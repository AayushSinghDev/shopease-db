from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.core.paginator import Paginator
from .models import Customer, Seller
from products.models import Product, Category
from orders.models import Order, OrderItem


def check_admin(request):
    return request.session.get('user_role') == 'admin'


# ── SELLERS ───────────────────────────────────────────────────
def admin_sellers(request):
    if not check_admin(request): return redirect('/accounts/login/')
    if request.method == 'POST':
        action = request.POST.get('action')
        seller = get_object_or_404(Seller, id=request.POST.get('seller_id'))
        if action == 'approve':
            seller.is_approved = True
            seller.save()
            messages.success(request, f'Seller "{seller.name}" approved!')
        elif action == 'reject':
            seller.is_approved = False
            seller.save()
            messages.warning(request, f'Seller "{seller.name}" approval revoked.')
        elif action == 'delete':
            name = seller.name
            seller.delete()
            messages.success(request, f'Seller "{name}" deleted.')
        return redirect('/admin-panel/sellers/')

    sellers = Seller.objects.all().order_by('-id')
    return render(request, 'admin_panel/sellers.html', {
        'sellers':       sellers,
        'pending_count': sellers.filter(is_approved=False).count(),
        'approved_count': sellers.filter(is_approved=True).count(),
    })


def admin_seller_detail(request, seller_id):
    if not check_admin(request): return redirect('/accounts/login/')
    seller      = get_object_or_404(Seller, id=seller_id)
    products    = Product.objects.filter(seller=seller).select_related('category')
    order_items = OrderItem.objects.filter(product__seller=seller).select_related('order', 'product')
    order_ids   = order_items.values_list('order_id', flat=True).distinct()
    orders      = Order.objects.filter(id__in=order_ids).order_by('-created_at')
    from django.db.models import Sum
    total_earnings = orders.exclude(status='cancelled').aggregate(t=Sum('total'))['t'] or 0
    return render(request, 'admin_panel/seller_detail.html', {
        'seller': seller, 'products': products,
        'orders': orders, 'total_earnings': total_earnings,
    })


# ── CUSTOMERS ─────────────────────────────────────────────────
def admin_customers(request):
    if not check_admin(request): return redirect('/accounts/login/')
    if request.method == 'POST':
        customer = get_object_or_404(Customer, id=request.POST.get('customer_id'))
        name = customer.name
        customer.delete()
        messages.success(request, f'Customer "{name}" deleted.')
        return redirect('/admin-panel/customers/')

    search     = request.GET.get('search', '').strip()
    customers  = Customer.objects.all().order_by('-id')
    if search:
        customers = customers.filter(name__icontains=search) | customers.filter(email__icontains=search)

    paginator = Paginator(customers, 25)
    page_obj  = paginator.get_page(request.GET.get('page', 1))
    return render(request, 'admin_panel/customers.html', {
        'customers': page_obj,
        'search':    search,
    })


def admin_customer_detail(request, customer_id):
    if not check_admin(request): return redirect('/accounts/login/')
    customer = get_object_or_404(Customer, id=customer_id)
    orders   = Order.objects.filter(customer=customer).prefetch_related('items').order_by('-created_at')
    from products.models import Wishlist, Review
    from django.db.models import Sum
    wishlist    = Wishlist.objects.filter(customer=customer).select_related('product')
    reviews     = Review.objects.filter(customer=customer).select_related('product')
    total_spent = orders.exclude(status='cancelled').aggregate(t=Sum('total'))['t'] or 0
    return render(request, 'admin_panel/customer_detail.html', {
        'customer': customer, 'orders': orders,
        'wishlist': wishlist, 'reviews': reviews, 'total_spent': total_spent,
    })


# ── PRODUCTS ──────────────────────────────────────────────────
def admin_products(request):
    if not check_admin(request): return redirect('/accounts/login/')
    if request.method == 'POST':
        product = get_object_or_404(Product, id=request.POST.get('product_id'))
        name = product.name
        product.delete()
        messages.success(request, f'Product "{name}" deleted.')
        return redirect('/admin-panel/products/')

    products  = Product.objects.all().select_related('seller', 'category').order_by('-id')
    paginator = Paginator(products, 25)
    page_obj  = paginator.get_page(request.GET.get('page', 1))
    return render(request, 'admin_panel/products.html', {'products': page_obj})


def admin_product_detail(request, product_id):
    if not check_admin(request): return redirect('/accounts/login/')
    product = get_object_or_404(Product, id=product_id)
    reviews = product.reviews.select_related('customer').order_by('-created_at')
    try:    variants = list(product.variants.all())
    except: variants = []
    try:    images   = list(product.extra_images.all())
    except: images   = []
    order_items = OrderItem.objects.filter(product=product).select_related(
        'order', 'order__customer').order_by('-order__created_at')
    return render(request, 'admin_panel/product_detail.html', {
        'product': product, 'reviews': reviews,
        'variants': variants, 'images': images, 'order_items': order_items,
    })


# ── ORDERS ────────────────────────────────────────────────────
def admin_orders(request):
    if not check_admin(request): return redirect('/accounts/login/')
    if request.method == 'POST':
        order = get_object_or_404(Order, id=request.POST.get('order_id'))
        order.status = request.POST.get('status')
        order.save()
        messages.success(request, f'Order #{order.pk} updated.')
        try:
            from orders.views import send_status_email
            send_status_email(order.customer, order)
        except Exception:
            pass
        return redirect('/admin-panel/orders/')

    status_filter = request.GET.get('status', '')
    orders        = Order.objects.all().select_related('customer', 'address').prefetch_related('items').order_by('-created_at')
    if status_filter:
        orders = orders.filter(status=status_filter)

    paginator = Paginator(orders, 25)
    page_obj  = paginator.get_page(request.GET.get('page', 1))
    return render(request, 'admin_panel/orders.html', {
        'orders':        page_obj,
        'status_filter': status_filter,
    })


def admin_order_detail(request, order_id):
    if not check_admin(request): return redirect('/accounts/login/')
    order = get_object_or_404(Order, id=order_id)
    items = order.items.select_related('product')
    if request.method == 'POST':
        order.status = request.POST.get('status')
        order.save()
        messages.success(request, f'Order #{order.pk} updated to "{order.status}".')
        try:
            from orders.views import send_status_email
            send_status_email(order.customer, order)
        except Exception:
            pass
        return redirect(f'/admin-panel/orders/{order_id}/')
    return render(request, 'admin_panel/order_detail.html', {'order': order, 'items': items})


# ── CATEGORIES ────────────────────────────────────────────────
def admin_categories(request):
    if not check_admin(request): return redirect('/accounts/login/')
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'add':
            name = request.POST.get('name', '').strip()
            if name:
                if Category.objects.filter(name=name).exists():
                    messages.error(request, f'Category "{name}" already exists.')
                else:
                    image = request.FILES.get('image')
                    Category.objects.create(name=name, image=image)
                    messages.success(request, f'Category "{name}" added!')
            else:
                messages.error(request, 'Name cannot be empty.')
        elif action == 'delete':
            cat  = get_object_or_404(Category, id=request.POST.get('category_id'))
            name = cat.name
            cat.delete()
            messages.success(request, f'Category "{name}" deleted.')
        return redirect('/admin-panel/categories/')

    from django.db.models import Count
    categories = Category.objects.annotate(product_count=Count('products')).order_by('name')
    return render(request, 'admin_panel/categories.html', {'categories': categories})


def admin_category_detail(request, category_id):
    if not check_admin(request): return redirect('/accounts/login/')
    category = get_object_or_404(Category, id=category_id)
    products = Product.objects.filter(category=category).select_related('seller').order_by('-id')
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'delete_category':
            name = category.name
            category.delete()
            messages.success(request, f'Category "{name}" deleted.')
            return redirect('/admin-panel/categories/')
        elif action == 'delete_product':
            p    = get_object_or_404(Product, id=request.POST.get('product_id'))
            name = p.name
            p.delete()
            messages.success(request, f'Product "{name}" deleted.')
            return redirect(f'/admin-panel/categories/{category_id}/')
    return render(request, 'admin_panel/category_detail.html', {
        'category': category, 'products': products,
    })


# ── REVENUE ───────────────────────────────────────────────────
def admin_revenue(request):
    if not check_admin(request): return redirect('/accounts/login/')
    from django.db.models import Sum
    from datetime import datetime
    import json

    filter_seller = request.GET.get('seller', '')
    filter_status = request.GET.get('status', '')

    orders_qs = Order.objects.all()
    if filter_seller:
        try:
            orders_qs = orders_qs.filter(items__product__seller_id=int(filter_seller)).distinct()
        except Exception:
            pass
    if filter_status:
        orders_qs = orders_qs.filter(status=filter_status)

    completed_qs     = orders_qs.exclude(status='cancelled')
    total_revenue    = completed_qs.aggregate(t=Sum('total'))['t'] or 0
    total_orders     = orders_qs.count()
    pending_orders   = orders_qs.filter(status='pending').count()
    delivered_orders = orders_qs.filter(status='delivered').count()
    cancelled_orders = orders_qs.filter(status='cancelled').count()

    months_dict = {}
    for o in completed_qs.values('created_at', 'total'):
        try:
            key = o['created_at'].strftime('%b %Y')
            months_dict[key] = months_dict.get(key, 0) + float(o['total'] or 0)
        except Exception:
            pass

    sorted_months = sorted(months_dict.items(), key=lambda x: datetime.strptime(x[0], '%b %Y'))
    months_labels = [m[0] for m in sorted_months]
    months_data   = [round(m[1], 2) for m in sorted_months]

    status_data = {
        'Pending':   orders_qs.filter(status='pending').count(),
        'Confirmed': orders_qs.filter(status='confirmed').count(),
        'Shipped':   orders_qs.filter(status='shipped').count(),
        'Delivered': delivered_orders,
        'Cancelled': cancelled_orders,
    }

    from accounts.models import Seller as SellerModel
    sellers = SellerModel.objects.all()

    return render(request, 'admin_panel/revenue.html', {
        'total_revenue':    total_revenue,
        'months_labels':    json.dumps(months_labels),
        'months_data':      json.dumps(months_data),
        'status_data':      json.dumps(status_data),
        'total_orders':     total_orders,
        'pending_orders':   pending_orders,
        'delivered_orders': delivered_orders,
        'cancelled_orders': cancelled_orders,
        'sellers':          sellers,
        'filter_seller':    filter_seller,
        'filter_status':    filter_status,
    })


# ── REVIEWS ───────────────────────────────────────────────────
def admin_reviews(request):
    if not check_admin(request): return redirect('/accounts/login/')
    from products.models import Review

    if request.method == 'POST':
        review_id = request.POST.get('review_id')
        try:
            r = Review.objects.get(id=review_id)
            r.delete()
            messages.success(request, 'Review deleted.')
        except Review.DoesNotExist:
            messages.error(request, 'Review not found.')
        return redirect('/admin-panel/reviews/')

    filter_rating  = request.GET.get('rating', '')
    filter_product = request.GET.get('product', '')

    reviews_qs = Review.objects.select_related('product', 'customer').order_by('-created_at')
    if filter_rating:
        reviews_qs = reviews_qs.filter(rating=int(filter_rating))
    if filter_product:
        reviews_qs = reviews_qs.filter(product_id=int(filter_product))

    from django.db.models import Avg
    total_reviews = reviews_qs.count()
    avg_rating    = round(reviews_qs.aggregate(a=Avg('rating'))['a'] or 0, 1)
    five_star     = reviews_qs.filter(rating=5).count()
    one_star      = reviews_qs.filter(rating=1).count()
    with_comment  = reviews_qs.exclude(comment='').count()

    paginator    = Paginator(reviews_qs, 20)
    page_obj     = paginator.get_page(request.GET.get('page', 1))
    all_products = Product.objects.all().order_by('name')

    return render(request, 'admin_panel/reviews.html', {
        'reviews':        page_obj,
        'total_reviews':  total_reviews,
        'avg_rating':     avg_rating,
        'five_star':      five_star,
        'one_star':       one_star,
        'with_comment':   with_comment,
        'all_products':   all_products,
        'filter_rating':  filter_rating,
        'filter_product': filter_product,
    })


def admin_delete_review(request, review_id):
    if not check_admin(request): return redirect('/accounts/login/')
    if request.method == 'POST':
        from products.models import Review
        try:
            r = Review.objects.get(id=review_id)
            r.delete()
            messages.success(request, 'Review deleted.')
        except Review.DoesNotExist:
            messages.error(request, 'Review not found.')
    return redirect('/admin-panel/reviews/')
