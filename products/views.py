from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Avg, Count
from .models import Product, Category, Wishlist, Review
from accounts.models import Seller, Customer


def home(request):
    # Annotate to avoid N+1 on avg_rating/review_count
    featured = (
        Product.objects
        .filter(stock__gt=0)
        .select_related('category', 'seller')
        .annotate(avg_r=Avg('reviews__rating'), rev_count=Count('reviews'))
        .order_by('-created_at')[:8]
    )
    categories = Category.objects.all()
    return render(request, 'products/home.html', {
        'featured':        featured,
        'categories':      categories,
        'total_products':  Product.objects.count(),
        'total_sellers':   Seller.objects.filter(is_approved=True).count(),
        'total_customers': 0,
    })


def shop(request):
    products     = Product.objects.select_related('category', 'seller').all()
    categories   = Category.objects.all()
    search_query = request.GET.get('search', '').strip()
    category_id  = request.GET.get('category', '')
    sort         = request.GET.get('sort', '')

    if search_query:
        products = products.filter(name__icontains=search_query)

    if category_id:
        try:
            cat      = Category.objects.get(id=int(category_id))
            products = products.filter(category=cat)
        except (Category.DoesNotExist, ValueError):
            pass

    if sort == 'price_low':
        products = products.order_by('price')
    elif sort == 'price_high':
        products = products.order_by('-price')
    else:
        products = products.order_by('-created_at')

    # ── Annotate avg rating + review count in ONE query (fixes N+1) ──
    products = products.annotate(avg_r=Avg('reviews__rating'), rev_count=Count('reviews'))

    # ── Pagination: 24 products per page ──
    paginator = Paginator(products, 24)
    page_num  = request.GET.get('page', 1)
    page_obj  = paginator.get_page(page_num)

    # Wishlist IDs for logged-in customer
    wishlist_ids = []
    customer = None
    if request.session.get('user_role') == 'customer':
        try:
            customer     = Customer.objects.get(id=request.session['user_id'])
            wishlist_ids = list(Wishlist.objects.filter(customer=customer)
                                .values_list('product_id', flat=True))
        except Customer.DoesNotExist:
            pass

    return render(request, 'products/shop.html', {
        'products':      page_obj,
        'page_obj':      page_obj,
        'categories':    categories,
        'search_query':  search_query,
        'category_id':   category_id,
        'sort':          sort,
        'wishlist_ids':  wishlist_ids,
        'customer':      customer,
    })


def product_detail(request, pk):
    product = get_object_or_404(Product, pk=pk)
    reviews = product.reviews.select_related('customer').order_by('-created_at')

    customer    = None
    user_review = None
    in_wishlist = False

    if request.session.get('user_role') == 'customer':
        try:
            customer    = Customer.objects.get(id=request.session['user_id'])
            user_review = Review.objects.filter(product=product, customer=customer).first()
            in_wishlist = Wishlist.objects.filter(customer=customer, product=product).exists()
        except Customer.DoesNotExist:
            pass

    if request.method == 'POST' and request.session.get('user_role') == 'customer' and customer:
        action = request.POST.get('action')
        if action == 'review':
            if user_review:
                messages.error(request, 'You have already reviewed this product.')
            else:
                rating  = request.POST.get('rating')
                comment = request.POST.get('comment', '').strip()
                if rating:
                    Review.objects.create(
                        product=product, customer=customer,
                        rating=int(rating), comment=comment,
                    )
                    messages.success(request, 'Review submitted!')
            return redirect(f'/products/detail/{pk}/')

    related = (
        Product.objects.filter(category=product.category)
        .exclude(id=product.id)
        .select_related('category', 'seller')
        .annotate(avg_r=Avg('reviews__rating'), rev_count=Count('reviews'))[:6]
    )

    return render(request, 'products/detail.html', {
        'product':      product,
        'reviews':      reviews,
        'user_review':  user_review,
        'in_wishlist':  in_wishlist,
        'customer':     customer,
        'related':      related,
        'all_images':   product.all_images(),
    })


def toggle_wishlist(request, pk):
    if request.session.get('user_role') != 'customer':
        messages.warning(request, 'Please login to use wishlist.')
        return redirect('/accounts/login/')
    try:
        customer = Customer.objects.get(id=request.session['user_id'])
    except Customer.DoesNotExist:
        return redirect('/accounts/login/')

    product = get_object_or_404(Product, pk=pk)
    item    = Wishlist.objects.filter(customer=customer, product=product).first()
    if item:
        item.delete()
        messages.success(request, f'"{product.name}" removed from wishlist.')
    else:
        Wishlist.objects.create(customer=customer, product=product)
        messages.success(request, f'"{product.name}" added to wishlist!')

    return redirect(request.META.get('HTTP_REFERER', '/products/'))


def wishlist(request):
    if request.session.get('user_role') != 'customer':
        messages.warning(request, 'Please login to view your wishlist.')
        return redirect('/accounts/login/')
    try:
        customer = Customer.objects.get(id=request.session['user_id'])
    except Customer.DoesNotExist:
        return redirect('/accounts/login/')

    wishlist_items = (Wishlist.objects.filter(customer=customer)
                      .select_related('product', 'product__category')
                      .order_by('-added_at'))
    return render(request, 'products/wishlist.html', {
        'wishlist_items': wishlist_items,
        'customer':       customer,
    })


def category_list(request):
    categories = Category.objects.all()
    return render(request, 'products/category_list.html', {'categories': categories})
