def cart_qty(request):
    """
    Injects cart_qty (total item quantity) into every template context.
    This fixes the bug where |length only counted unique products, not total qty.
    """
    cart = request.session.get('cart', {})
    total_qty = sum(cart.values()) if cart else 0
    return {'cart_qty': total_qty}
