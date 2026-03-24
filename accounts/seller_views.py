from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from products.models import Product, Category, ProductImage, ProductVariant
from orders.models import Order, OrderItem
from accounts.models import Seller
import os


def seller_required(request):
    """
    Returns True only if the user is logged in as an approved seller.
    Checks both session role AND database approval status.
    """
    if request.session.get('user_role') != 'seller':
        return False
    try:
        seller = Seller.objects.get(id=request.session['user_id'])
        return seller.is_approved
    except Seller.DoesNotExist:
        return False


def _get_seller(request):
    return Seller.objects.get(id=request.session['user_id'])


# ── SELLER DASHBOARD ──────────────────────────────────────────
def seller_dashboard(request):
    if not seller_required(request):
        messages.error(request, 'Please login as an approved seller.')
        return redirect('/accounts/login/')

    seller   = _get_seller(request)
    products = Product.objects.filter(seller=seller)

    order_items    = OrderItem.objects.filter(product__seller=seller).select_related('order', 'product')
    order_ids      = order_items.values_list('order_id', flat=True).distinct()
    orders         = Order.objects.filter(id__in=order_ids)
    total_products = products.count()
    total_orders   = orders.count()
    total_earnings = sum(o.total for o in orders if o.status != 'cancelled')
    recent_orders  = orders.order_by('-created_at')[:5]

    return render(request, 'seller/dashboard.html', {
        'seller':         seller,
        'total_products': total_products,
        'total_orders':   total_orders,
        'total_earnings': total_earnings,
        'recent_orders':  recent_orders,
        'products':       products[:4],
    })


# ── SELLER PRODUCTS ───────────────────────────────────────────
def seller_products(request):
    if not seller_required(request):
        return redirect('/accounts/login/')

    seller   = _get_seller(request)
    products = Product.objects.filter(seller=seller).select_related('category').order_by('-id')

    return render(request, 'seller/products.html', {
        'seller':   seller,
        'products': products,
    })


# ── ADD PRODUCT ───────────────────────────────────────────────
def add_product(request):
    if not seller_required(request):
        return redirect('/accounts/login/')

    seller     = _get_seller(request)
    categories = Category.objects.all()

    if request.method == 'POST':
        name        = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        price       = request.POST.get('price')
        stock       = request.POST.get('stock')
        category_id = request.POST.get('category')
        image       = request.FILES.get('image')

        if not name or not price or not stock:
            messages.error(request, 'Name, price and stock are required.')
            return render(request, 'seller/add_product.html',
                          {'categories': categories, 'seller': seller})

        # ── File type validation ───────────────────────────────
        ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'webp', 'gif'}
        MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB
        if image:
            ext = image.name.rsplit('.', 1)[-1].lower()
            if ext not in ALLOWED_EXTENSIONS:
                messages.error(request, 'Only JPG, PNG, WEBP, GIF images are allowed.')
                return render(request, 'seller/add_product.html',
                              {'categories': categories, 'seller': seller})
            if image.size > MAX_FILE_SIZE:
                messages.error(request, 'Image must be under 5 MB.')
                return render(request, 'seller/add_product.html',
                              {'categories': categories, 'seller': seller})

        category = None
        if category_id:
            try:
                category = Category.objects.get(id=category_id)
            except Category.DoesNotExist:
                pass

        product = Product.objects.create(
            name=name, description=description,
            price=price, stock=stock,
            category=category, seller=seller, image=image,
        )

        # Save extra images (image_2 to image_8)
        for i in range(2, 9):
            extra_img = request.FILES.get(f'image_{i}')
            if extra_img:
                ext = extra_img.name.rsplit('.', 1)[-1].lower()
                if ext in ALLOWED_EXTENSIONS and extra_img.size <= MAX_FILE_SIZE:
                    ProductImage.objects.create(product=product, image=extra_img,
                                                order=i-1, is_primary=False)

        _save_variants(request, product)
        messages.success(request, f'Product "{product.name}" added successfully!')
        return redirect('/seller/products/')

    return render(request, 'seller/add_product.html', {
        'categories':    categories,
        'seller':        seller,
        'variant_types': ProductVariant.VARIANT_TYPES,
    })


# ── EDIT PRODUCT ──────────────────────────────────────────────
def edit_product(request, pk):
    if not seller_required(request):
        return redirect('/accounts/login/')

    seller     = _get_seller(request)
    product    = get_object_or_404(Product, pk=pk, seller=seller)
    categories = Category.objects.all()

    if request.method == 'POST':
        product.name        = request.POST.get('name', '').strip()
        product.description = request.POST.get('description', '').strip()
        product.price       = request.POST.get('price')
        product.stock       = request.POST.get('stock')
        category_id         = request.POST.get('category')
        image               = request.FILES.get('image')

        ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'webp', 'gif'}
        MAX_FILE_SIZE = 5 * 1024 * 1024

        if category_id:
            try:
                product.category = Category.objects.get(id=category_id)
            except Category.DoesNotExist:
                product.category = None
        if image:
            ext = image.name.rsplit('.', 1)[-1].lower()
            if ext in ALLOWED_EXTENSIONS and image.size <= MAX_FILE_SIZE:
                product.image = image

        product.save()

        delete_ids = request.POST.getlist('delete_image')
        if delete_ids:
            ProductImage.objects.filter(id__in=delete_ids, product=product).delete()

        for i in range(2, 9):
            extra_img = request.FILES.get(f'image_{i}')
            if extra_img:
                ext = extra_img.name.rsplit('.', 1)[-1].lower()
                if ext in ALLOWED_EXTENSIONS and extra_img.size <= MAX_FILE_SIZE:
                    if product.extra_images.count() < 7:
                        count = product.extra_images.count()
                        ProductImage.objects.create(product=product, image=extra_img,
                                                    order=count+1, is_primary=False)

        product.variants.all().delete()
        _save_variants(request, product)

        messages.success(request, f'Product "{product.name}" updated!')
        return redirect('/seller/products/')

    return render(request, 'seller/edit_product.html', {
        'product':       product,
        'categories':    categories,
        'seller':        seller,
        'extra_images':  product.extra_images.all(),
        'variants':      product.variants.all(),
        'variant_types': ProductVariant.VARIANT_TYPES,
    })


def _save_variants(request, product):
    """Read variant rows from POST and save them."""
    v_types  = request.POST.getlist('variant_type[]')
    v_values = request.POST.getlist('variant_value[]')
    v_prices = request.POST.getlist('variant_price[]')
    v_stocks = request.POST.getlist('variant_stock[]')

    for i, val in enumerate(v_values):
        val = val.strip()
        if not val:
            continue
        try:
            price_extra = float(v_prices[i]) if i < len(v_prices) and v_prices[i] else 0
            stk         = int(v_stocks[i])   if i < len(v_stocks)  and v_stocks[i]  else 0
            vtype       = v_types[i]         if i < len(v_types)                     else 'other'
        except (ValueError, IndexError):
            price_extra, stk, vtype = 0, 0, 'other'
        ProductVariant.objects.create(
            product=product, variant_type=vtype,
            value=val, price_extra=price_extra, stock=stk,
        )


# ── DELETE PRODUCT ────────────────────────────────────────────
def delete_product(request, pk):
    if not seller_required(request):
        return redirect('/accounts/login/')
    if request.method != 'POST':
        return redirect('/seller/products/')
    seller  = _get_seller(request)
    product = get_object_or_404(Product, pk=pk, seller=seller)
    name    = product.name
    product.delete()
    messages.success(request, f'Product "{name}" deleted.')
    return redirect('/seller/products/')


# ── SELLER ORDERS ─────────────────────────────────────────────
def seller_orders(request):
    if not seller_required(request):
        return redirect('/accounts/login/')

    seller      = _get_seller(request)
    order_items = OrderItem.objects.filter(
        product__seller=seller
    ).select_related('order', 'product', 'order__customer', 'order__address').order_by('-order__created_at')

    return render(request, 'seller/orders.html', {
        'seller':      seller,
        'order_items': order_items,
    })


# ── UPDATE ORDER STATUS ───────────────────────────────────────
def update_order_status(request, pk):
    if not seller_required(request):
        return redirect('/accounts/login/')

    seller = _get_seller(request)
    order  = get_object_or_404(Order, pk=pk)

    if not OrderItem.objects.filter(order=order, product__seller=seller).exists():
        messages.error(request, 'You do not have permission to update this order.')
        return redirect('/seller/orders/')

    if request.method == 'POST':
        new_status = request.POST.get('status')
        # Sellers cannot set 'cancelled' — only customers can cancel orders
        valid = ['pending', 'confirmed', 'shipped', 'delivered']
        if new_status in valid:
            order.status = new_status
            order.save()
            messages.success(request, f'Order #{order.pk} updated to "{new_status}".')
            try:
                from orders.views import send_status_email
                send_status_email(order.customer, order)
            except Exception:
                pass
        else:
            messages.error(request, 'Invalid status selected.')

    return redirect('/seller/orders/')


# ── SELLER DISCOUNTS ──────────────────────────────────────────
def seller_discounts(request):
    if not seller_required(request):
        return redirect('/accounts/login/')

    from discounts.models import DiscountCode
    seller = _get_seller(request)
    codes  = DiscountCode.objects.filter(created_by=seller).order_by('-created_at')

    return render(request, 'seller/discounts.html', {
        'seller': seller,
        'codes':  codes,
    })
