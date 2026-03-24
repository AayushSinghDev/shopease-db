import hmac
import hashlib
import json
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib import messages
from django.db import transaction
from django.db.models import F
from products.models import Product
from .models import Order, OrderItem, Address
from accounts.models import Customer
from decimal import Decimal


# ── CART HELPERS ──────────────────────────────────────────────
def get_cart(request):
    return request.session.get('cart', {})

def save_cart(request, cart):
    request.session['cart'] = cart
    request.session.modified = True

def get_cart_totals(request):
    cart, cart_items, cart_total = get_cart(request), [], Decimal('0')
    for product_id, quantity in cart.items():
        try:
            product  = Product.objects.get(id=int(product_id))
            subtotal = product.price * quantity
            cart_total += subtotal
            cart_items.append({'product': product, 'quantity': quantity,
                                'subtotal': round(subtotal, 2)})
        except Product.DoesNotExist:
            pass
    discount_amount  = Decimal(str(request.session.get('discount_amount', 0)))
    discounted_total = max(cart_total - discount_amount, Decimal('0'))
    shipping         = Decimal('0') if discounted_total >= 499 else (Decimal('49') if cart_items else Decimal('0'))
    tax              = round(discounted_total * Decimal('0.05'), 2)
    grand_total      = round(discounted_total + shipping + tax, 2)

    # Cart total quantity (sum of all quantities, not unique item count)
    cart_total_qty = sum(cart.values()) if cart else 0

    return {
        'cart_items':       cart_items,
        'cart_total':       round(cart_total, 2),
        'discount_amount':  round(discount_amount, 2),
        'discounted_total': round(discounted_total, 2),
        'tax':              tax,
        'shipping':         shipping,
        'grand_total':      grand_total,
        'discount_code':    request.session.get('discount_code', ''),
        'cart_total_qty':   cart_total_qty,
    }


# ── CART VIEWS ────────────────────────────────────────────────
def cart_view(request):
    return render(request, 'orders/cart.html', get_cart_totals(request))

def add_to_cart(request, product_id):
    if request.method == 'POST':
        product  = get_object_or_404(Product, id=product_id)
        quantity = int(request.POST.get('quantity', 1))
        cart = get_cart(request)
        pid  = str(product_id)
        cart[pid] = min(cart.get(pid, 0) + quantity, product.stock)
        save_cart(request, cart)
        messages.success(request, f'"{product.name}" added to cart!')
    return redirect(request.META.get('HTTP_REFERER', '/products/'))

def increase_quantity(request, product_id):
    cart, pid = get_cart(request), str(product_id)
    if pid in cart:
        product = get_object_or_404(Product, id=product_id)
        if cart[pid] < product.stock:
            cart[pid] += 1
            save_cart(request, cart)
    return redirect('/cart/')

def decrease_quantity(request, product_id):
    cart, pid = get_cart(request), str(product_id)
    if pid in cart:
        if cart[pid] > 1:
            cart[pid] -= 1
        else:
            del cart[pid]
        save_cart(request, cart)
    return redirect('/cart/')

def remove_from_cart(request, product_id):
    cart, pid = get_cart(request), str(product_id)
    if pid in cart:
        del cart[pid]
        save_cart(request, cart)
        messages.success(request, 'Item removed from cart.')
    return redirect('/cart/')

def clear_cart(request):
    request.session['cart'] = {}
    request.session.modified = True
    messages.success(request, 'Cart cleared.')
    return redirect('/cart/')


# ── CHECKOUT ──────────────────────────────────────────────────
def checkout(request):
    if not request.session.get('user_id'):
        messages.warning(request, 'Please login to continue.')
        return redirect('/accounts/login/')
    if request.session.get('user_role') != 'customer':
        messages.error(request, 'Only customers can place orders.')
        return redirect('/cart/')

    cart = get_cart(request)
    if not cart:
        messages.warning(request, 'Your cart is empty.')
        return redirect('/cart/')

    customer        = get_object_or_404(Customer, id=request.session['user_id'])
    totals          = get_cart_totals(request)
    saved_addresses = Address.objects.filter(customer=customer)

    if request.method == 'POST':
        payment_method = request.POST.get('payment_method', 'cod')

        saved_addr_id = request.POST.get('use_saved_address', '').strip()
        if saved_addr_id:
            address = get_object_or_404(Address, id=saved_addr_id, customer=customer)
        else:
            name    = request.POST.get('name', '').strip() or customer.name
            phone   = request.POST.get('phone', '').strip()
            house   = request.POST.get('house', '').strip()
            city    = request.POST.get('city', '').strip()
            state   = request.POST.get('state', '').strip()
            pincode = request.POST.get('pincode', '').strip()
            if not house or not city or not state or not pincode:
                messages.error(request, 'Please fill all address fields.')
                return render(request, 'orders/checkout.html',
                              {**totals, 'saved_addresses': saved_addresses, 'customer': customer})
            address = Address.objects.create(
                customer=customer, name=name, full_name=name,
                phone=phone, house=house, city=city, state=state, pincode=pincode,
            )

        # ── Stock check before placing order ──────────────────
        stock_errors = _check_stock_availability(cart)
        if stock_errors:
            for err in stock_errors:
                messages.error(request, err)
            return render(request, 'orders/checkout.html',
                          {**totals, 'saved_addresses': saved_addresses, 'customer': customer})

        request.session['checkout_address_id'] = address.id
        request.session.modified = True

        if payment_method == 'razorpay':
            return redirect('/cart/razorpay/create/')

        # ── COD Flow — atomic to prevent race conditions ──────
        try:
            order = _create_order_atomic(
                customer=customer, address=address,
                payment_method='cod', payment_status='pending',
                totals=totals, cart=cart,
            )
        except ValueError as e:
            messages.error(request, str(e))
            return redirect('/cart/')

        _apply_discount(totals)
        _send_order_email(customer, order)

        request.session.pop('cart', None)
        request.session.pop('discount_code', None)
        request.session.pop('discount_amount', None)
        request.session['last_order_id']    = order.id
        request.session['last_grand_total'] = float(totals['grand_total'])
        request.session.modified = True
        messages.success(request, 'Order placed successfully! 🎉')
        return redirect('/cart/confirmation/')

    return render(request, 'orders/checkout.html', {
        **totals, 'saved_addresses': saved_addresses, 'customer': customer,
    })


def _check_stock_availability(cart):
    """Returns list of error strings for out-of-stock items."""
    errors = []
    for pid, qty in cart.items():
        try:
            product = Product.objects.get(id=int(pid))
            if product.stock < qty:
                if product.stock == 0:
                    errors.append(f'"{product.name}" is out of stock.')
                else:
                    errors.append(
                        f'"{product.name}" only has {product.stock} unit(s) left '
                        f'(you have {qty} in cart).'
                    )
        except Product.DoesNotExist:
            errors.append(f'A product in your cart is no longer available.')
    return errors


@transaction.atomic
def _create_order_atomic(customer, address, payment_method, payment_status,
                          totals, cart, payment_id=None, razorpay_order_id=None):
    """
    Creates order and deducts stock atomically using select_for_update.
    Raises ValueError if stock is insufficient at the time of order creation.
    """
    order = Order.objects.create(
        customer=customer, address=address,
        payment_method=payment_method,
        payment_status=payment_status,
        payment_id=payment_id,
        razorpay_order_id=razorpay_order_id,
        discount_code=totals['discount_code'] or '',
        discount_amount=totals['discount_amount'],
        subtotal=totals['cart_total'],
        shipping=totals['shipping'],
        tax=totals['tax'],
        total=totals['grand_total'],
    )

    for pid, qty in cart.items():
        try:
            # Lock the product row to prevent race conditions
            product = Product.objects.select_for_update().get(id=int(pid))
            if product.stock < qty:
                raise ValueError(
                    f'Sorry, "{product.name}" went out of stock just now. '
                    f'Please update your cart.'
                )
            OrderItem.objects.create(
                order=order, product=product,
                product_name=product.name, product_price=product.price,
                quantity=qty, subtotal=round(float(product.price) * qty, 2),
            )
            # Use F() expression to avoid race condition on stock update
            Product.objects.filter(id=product.id).update(stock=F('stock') - qty)
        except Product.DoesNotExist:
            pass

    return order


def _apply_discount(totals):
    if totals['discount_code']:
        try:
            from discounts.models import DiscountCode
            # Use F() to atomically increment used_count — prevents race condition
            DiscountCode.objects.filter(code=totals['discount_code']).update(
                used_count=F('used_count') + 1
            )
        except Exception:
            pass


# ── RAZORPAY VIEWS ────────────────────────────────────────────
def razorpay_create_order(request):
    """Create Razorpay order and redirect to payment page."""
    if not request.session.get('user_id'):
        return redirect('/accounts/login/')

    from django.conf import settings

    key_id     = getattr(settings, 'RAZORPAY_KEY_ID', '')
    key_secret = getattr(settings, 'RAZORPAY_KEY_SECRET', '')

    cart   = get_cart(request)
    totals = get_cart_totals(request)

    if not cart:
        messages.warning(request, 'Your cart is empty.')
        return redirect('/cart/')

    amount_paise = int(float(totals['grand_total']) * 100)

    if key_id and key_secret:
        try:
            import razorpay
            client = razorpay.Client(auth=(key_id, key_secret))
            rzp_order = client.order.create({
                'amount':          amount_paise,
                'currency':        'INR',
                'payment_capture': 1,
            })
            request.session['razorpay_order_id'] = rzp_order['id']
        except Exception as e:
            messages.error(request, f'Payment gateway error: {e}')
            return redirect('/cart/checkout/')
    else:
        # No keys configured — use Razorpay test/demo mode only
        request.session['razorpay_order_id'] = 'rzp_demo_' + str(int(float(totals['grand_total'])))

    request.session.modified = True
    return redirect('/cart/razorpay/payment/')


def razorpay_payment_page(request):
    """Show Razorpay payment page."""
    if not request.session.get('user_id'):
        return redirect('/accounts/login/')

    from django.conf import settings
    totals       = get_cart_totals(request)
    customer     = get_object_or_404(Customer, id=request.session['user_id'])
    rzp_order_id = request.session.get('razorpay_order_id', '')

    if not rzp_order_id:
        messages.error(request, 'Payment session expired. Please try again.')
        return redirect('/cart/checkout/')

    key_id    = getattr(settings, 'RAZORPAY_KEY_ID', '')
    demo_mode = not key_id

    return render(request, 'orders/razorpay_payment.html', {
        **totals,
        'customer':     customer,
        'rzp_order_id': rzp_order_id,
        'rzp_key_id':   key_id,
        'demo_mode':    demo_mode,
        'amount_paise': int(float(totals['grand_total']) * 100),
    })


def razorpay_verify(request):
    """Verify Razorpay payment signature and create order."""
    if request.method != 'POST':
        return redirect('/cart/')
    if not request.session.get('user_id'):
        return redirect('/accounts/login/')

    from django.conf import settings

    payment_id   = request.POST.get('razorpay_payment_id', '')
    rzp_order_id = request.POST.get('razorpay_order_id', '')
    signature    = request.POST.get('razorpay_signature', '')

    # ── SECURITY: demo_payment bypass REMOVED ─────────────────
    # Do NOT add any shortcut that skips payment verification.
    # Use Razorpay test mode (rzp_test_* keys) for development testing.

    key_secret = getattr(settings, 'RAZORPAY_KEY_SECRET', '')
    customer   = get_object_or_404(Customer, id=request.session['user_id'])
    totals     = get_cart_totals(request)
    cart       = get_cart(request)
    address_id = request.session.get('checkout_address_id')
    address    = get_object_or_404(Address, id=address_id) if address_id else None

    verified = False

    if key_secret and payment_id and signature:
        try:
            import razorpay
            client = razorpay.Client(auth=(getattr(settings, 'RAZORPAY_KEY_ID', ''), key_secret))
            params = {
                'razorpay_order_id':   rzp_order_id,
                'razorpay_payment_id': payment_id,
                'razorpay_signature':  signature,
            }
            client.utility.verify_payment_signature(params)
            verified = True
        except Exception:
            # Fallback HMAC manual check
            try:
                generated = hmac.new(
                    key_secret.encode(),
                    (rzp_order_id + '|' + payment_id).encode(),
                    hashlib.sha256,
                ).hexdigest()
                verified = hmac.compare_digest(generated, signature)
            except Exception:
                verified = False

    if verified:
        # ── Stock check before creating order ─────────────────
        stock_errors = _check_stock_availability(cart)
        if stock_errors:
            for err in stock_errors:
                messages.error(request, err)
            return redirect('/cart/')

        try:
            order = _create_order_atomic(
                customer=customer, address=address,
                payment_method='razorpay', payment_status='paid',
                totals=totals, cart=cart,
                payment_id=payment_id, razorpay_order_id=rzp_order_id,
            )
        except ValueError as e:
            messages.error(request, str(e))
            return redirect('/cart/')

        _apply_discount(totals)
        _send_order_email(customer, order)

        request.session.pop('cart', None)
        request.session.pop('discount_code', None)
        request.session.pop('discount_amount', None)
        request.session.pop('razorpay_order_id', None)
        request.session.pop('checkout_address_id', None)
        request.session['last_order_id']    = order.id
        request.session['last_grand_total'] = float(totals['grand_total'])
        request.session.modified = True
        messages.success(request, 'Payment successful! Order placed. 🎉')
        return redirect('/cart/confirmation/')
    else:
        messages.error(request, 'Payment verification failed. Please try again.')
        return redirect('/cart/razorpay/failed/')


def razorpay_failed(request):
    """Payment failed page."""
    return render(request, 'orders/razorpay_failed.html')


# ── EMAIL HELPERS ─────────────────────────────────────────────
def send_status_email(customer, order, old_status=None):
    """Send order status update email — silently fails if not configured."""
    try:
        from django.conf import settings
        if not settings.EMAIL_HOST_USER:
            return
        from django.core.mail import send_mail
        status_label = order.status.capitalize()
        subject  = f'Order #{order.pk} Status Updated — {status_label} | ShopEase'
        message  = (
            f'Hi {customer.name},\n\n'
            f'Your order #{order.pk} status has been updated to: {status_label}\n\n'
            f'Order Total: ₹{order.total}\n'
            f'Track your order: http://127.0.0.1:8000/cart/my-orders/{order.pk}/\n\n'
            f'Thank you for shopping with ShopEase!\n'
            f'Support: support@shopease.com'
        )
        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL,
                  [customer.email], fail_silently=True)
    except Exception:
        pass


def _send_order_email(customer, order):
    """Send order confirmation email to customer + seller notification."""
    try:
        from django.conf import settings
        if not settings.EMAIL_HOST_USER:
            return
        from django.core.mail import send_mail
        payment_label = ('Online Payment (Razorpay)'
                         if order.payment_method == 'razorpay'
                         else 'Cash on Delivery')

        # ── Email to Customer ──────────────────────────────────
        subject = f'Order #{order.pk} Confirmed — ShopEase'
        message = (
            f'Hi {customer.name},\n\n'
            f'Your order #{order.pk} has been placed successfully!\n\n'
            f'Total: ₹{order.total}\n'
            f'Payment: {payment_label}\n'
            f'Status: Pending\n\n'
            f'Track your order: http://127.0.0.1:8000/cart/my-orders/{order.pk}/\n\n'
            f'Thank you for shopping with ShopEase!\n'
            f'Support: support@shopease.com'
        )
        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL,
                  [customer.email], fail_silently=True)

        # ── Email to Seller(s) ────────────────────────────────
        try:
            sellers_notified = set()
            for item in order.items.select_related('product__seller'):
                if not item.product:
                    continue
                seller = item.product.seller
                if seller.id in sellers_notified:
                    continue
                sellers_notified.add(seller.id)
                seller_subject = f'🛒 New Order #{order.pk} — ShopEase'
                seller_message = (
                    f'Hi {seller.name},\n\n'
                    f'You received a new order!\n\n'
                    f'Order #: {order.pk}\n'
                    f'Customer: {customer.name}\n'
                    f'Payment: {payment_label}\n\n'
                    f'Items from your store:\n'
                )
                for it in order.items.filter(product__seller=seller):
                    seller_message += f'  - {it.product_name} x{it.quantity} = ₹{it.subtotal}\n'
                seller_message += (
                    f'\nPlease process and ship promptly.\n'
                    f'Manage: http://127.0.0.1:8000/seller/orders/\n\nShopEase Team'
                )
                send_mail(seller_subject, seller_message, settings.DEFAULT_FROM_EMAIL,
                          [seller.email], fail_silently=True)
        except Exception:
            pass

    except Exception:
        pass


# ── CONFIRMATION ──────────────────────────────────────────────
def confirmation(request):
    if request.session.get('user_role') != 'customer':
        return redirect('/accounts/login/')
    order_id    = request.session.get('last_order_id')
    grand_total = request.session.get('last_grand_total', 0)
    if not order_id:
        return redirect('/')
    order = get_object_or_404(Order, id=order_id)
    return render(request, 'orders/confirmation.html', {
        'order': order, 'items': order.items.select_related('product'),
        'grand_total': grand_total, 'address': order.address,
    })


# ── MY ORDERS ─────────────────────────────────────────────────
def my_orders(request):
    if request.session.get('user_role') != 'customer':
        messages.warning(request, 'Please login to view your orders.')
        return redirect('/accounts/login/')
    customer = get_object_or_404(Customer, id=request.session['user_id'])
    status   = request.GET.get('status', '')
    orders   = Order.objects.filter(customer=customer).prefetch_related('items__product').order_by('-created_at')
    if status:
        orders = orders.filter(status=status)
    return render(request, 'orders/my_orders.html', {
        'orders': orders, 'customer': customer, 'selected_status': status,
    })


# ── ORDER DETAIL ──────────────────────────────────────────────
def order_detail(request, pk):
    if request.session.get('user_role') != 'customer':
        return redirect('/accounts/login/')
    order = get_object_or_404(Order, pk=pk, customer_id=request.session['user_id'])
    return render(request, 'orders/order_detail.html', {
        'order': order, 'items': order.items.select_related('product'),
    })


# ── CANCEL ORDER ──────────────────────────────────────────────
def cancel_order(request, pk):
    if request.session.get('user_role') != 'customer':
        return redirect('/accounts/login/')
    order = get_object_or_404(Order, pk=pk, customer_id=request.session['user_id'])
    if order.status in ('pending', 'confirmed'):
        with transaction.atomic():
            for item in order.items.select_related('product'):
                if item.product:
                    # Atomic stock restore
                    Product.objects.filter(id=item.product.id).update(
                        stock=F('stock') + item.quantity
                    )
            order.status = 'cancelled'
            order.save(update_fields=['status'])
        messages.success(request, f'Order #{order.pk} cancelled. Stock restored.')
    else:
        messages.error(request, f'Cannot cancel order with status "{order.status}".')
    return redirect(f'/cart/my-orders/{pk}/')


# ── ADDRESS MANAGEMENT ────────────────────────────────────────
def delete_address(request, address_id):
    if request.session.get('user_role') != 'customer':
        return redirect('/accounts/login/')
    addr = get_object_or_404(Address, id=address_id, customer_id=request.session['user_id'])
    addr.delete()
    messages.success(request, 'Address deleted.')
    return redirect('/accounts/profile/')
