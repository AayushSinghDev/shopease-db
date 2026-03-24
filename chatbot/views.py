import json
import random
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from products.models import Product, Category


def get_system_prompt(request):
    role = request.session.get('user_role', '')
    name = request.session.get('user_name', '')
    base = (
        "You are ShopEase Assistant — a warm, helpful AI for an Indian e-commerce site. "
        "Be conversational, natural, friendly like a helpful friend. "
        "Keep replies SHORT (2-4 sentences max). Use emojis occasionally. "
        "You are NOT Claude and NOT made by Anthropic — you are ShopEase Assistant. "
        "Contact: support@shopease.com | +91 96879 07055 "
        "FREE shipping above Rs.499, Rs.49 below. 5% GST. Cash on Delivery only. "
    )
    if role == 'admin':
        return base + (
            f"You are talking to the ADMIN ({name}). "
            "Give real admin data when asked. Admin manages sellers, customers, products, orders, revenue. "
            "Admin URLs: /admin-panel/sellers/ /admin-panel/customers/ /admin-panel/products/ "
            "/admin-panel/orders/ /admin-panel/categories/ /admin-panel/revenue/ "
            "NEVER give customer shopping info or seller-specific earnings to admin queries."
        )
    elif role == 'seller':
        return base + (
            f"You are talking to SELLER ({name}). "
            "Help with managing products, orders, discounts, earnings. "
            "Seller URLs: /seller/dashboard/ /seller/products/ /seller/product/add/ "
            "/seller/orders/ /seller/discounts/ /accounts/seller-profile/ "
            "Sellers cannot buy products. NEVER give admin panel info to sellers."
        )
    else:
        cats = ', '.join(list(Category.objects.values_list('name', flat=True)[:6]))
        total = Product.objects.filter(stock__gt=0).count()
        user_ctx = f"Customer {name} is logged in. " if name else "User is browsing (not logged in). "
        return base + (
            f"{user_ctx}"
            f"ShopEase has {total} products in: {cats}. "
            "Customer URLs: /products/ /cart/ /cart/my-orders/ /products/wishlist/ /accounts/profile/ "
            "NEVER give admin or seller panel info to customers."
        )


@csrf_exempt
def chat(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST only'}, status=405)
    try:
        data     = json.loads(request.body)
        user_msg = data.get('message', '').strip()
        history  = data.get('history', [])
    except Exception:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    if not user_msg:
        return JsonResponse({'error': 'Empty'}, status=400)

    # Try Claude API first
    api_key = getattr(settings, 'ANTHROPIC_API_KEY', '').strip()
    if api_key:
        try:
            import urllib.request
            system_prompt = get_system_prompt(request)
            msgs = [h for h in history[-8:] if h.get('role') in ('user', 'assistant')]
            msgs.append({'role': 'user', 'content': user_msg})

            # Add live DB data to system for admin
            if request.session.get('user_role') == 'admin':
                system_prompt += _get_live_admin_data()

            payload = json.dumps({
                'model': 'claude-haiku-4-5-20251001',
                'max_tokens': 300,
                'system': system_prompt,
                'messages': msgs,
            }).encode()
            req = urllib.request.Request(
                'https://api.anthropic.com/v1/messages', data=payload,
                headers={
                    'Content-Type': 'application/json',
                    'x-api-key': api_key,
                    'anthropic-version': '2023-06-01',
                },
                method='POST',
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                result = json.loads(resp.read())
                bot_reply = result['content'][0]['text']
                _save_log(request, user_msg, bot_reply)
                return JsonResponse({'reply': bot_reply})
        except Exception:
            pass  # Fall through to keyword fallback

    # Keyword fallback (always works, no API needed)
    bot_reply = fallback_reply(user_msg, request)
    _save_log(request, user_msg, bot_reply)
    return JsonResponse({'reply': bot_reply})


def _get_live_admin_data():
    """Get live DB stats for admin chatbot context."""
    try:
        from accounts.models import Customer, Seller
        from orders.models import Order
        from django.db.models import Sum
        total_rev = Order.objects.exclude(status='cancelled').aggregate(t=Sum('total'))['t'] or 0
        return (
            f" LIVE DATA: {Customer.objects.count()} customers, "
            f"{Seller.objects.count()} sellers ({Seller.objects.filter(is_approved=False).count()} pending), "
            f"{Product.objects.count()} products, "
            f"{Order.objects.count()} orders, "
            f"Revenue: Rs.{float(total_rev):.0f}."
        )
    except Exception:
        return ""


def fallback_reply(msg, request):
    m    = msg.lower().strip()
    role = request.session.get('user_role', '')
    name = request.session.get('user_name', '')
    hi   = f", {name}!" if name else "!"

    # Greetings
    if any(w in m for w in ['hello','hi','hey','hii','namaste','hola','sup','wassup']):
        greets = {
            'admin':    f"Hey Admin{hi} 🛡️ I can show you seller counts, customer stats, revenue, orders, and more. What do you need?",
            'seller':   f"Hey{hi} 🏪 I can help with your products, orders, earnings, or discounts. What's up?",
        }
        default = f"Hey{hi} 👋 I'm ShopEase Assistant. Ask me about products, orders, shipping, or anything shopping-related!"
        return greets.get(role, default)

    if any(w in m for w in ['how are you','kaisa','kaise','how r u']):
        return "I'm great, always ready to help! 😊 What can I do for you?"

    if any(w in m for w in ['thank','thanks','ty','shukriya','dhanyawad']):
        return random.choice(["Anytime! 😊", "Happy to help! 🙌", "My pleasure! 😊"])

    if any(w in m for w in ['bye','goodbye','alvida','tata','ok bye']):
        return f"Bye{hi} 👋 Have a great day!"

    # ── ADMIN ──────────────────────────────────────────────────
    if role == 'admin':
        if any(w in m for w in ['seller','sellers','pending','approve','rejected']):
            try:
                from accounts.models import Seller
                total = Seller.objects.count()
                pending = Seller.objects.filter(is_approved=False).count()
                return f"You have {total} sellers total, {pending} pending approval. 🏪 <a href='/admin-panel/sellers/' style='color:#f5a623;font-weight:700;'>Manage Sellers →</a>"
            except Exception:
                return "Manage sellers at <a href='/admin-panel/sellers/' style='color:#f5a623;font-weight:700;'>Sellers Panel</a> 🏪"

        if any(w in m for w in ['customer','customers','user','users','buyers']):
            try:
                from accounts.models import Customer
                total = Customer.objects.count()
                return f"You have {total} registered customers. 👥 <a href='/admin-panel/customers/' style='color:#f5a623;font-weight:700;'>View All Customers →</a>"
            except Exception:
                return "View customers at <a href='/admin-panel/customers/' style='color:#f5a623;font-weight:700;'>Customers Panel</a> 👥"

        if any(w in m for w in ['product','products','item','items','listing']):
            total = Product.objects.count()
            return f"There are {total} products listed. 📦 <a href='/admin-panel/products/' style='color:#f5a623;font-weight:700;'>Manage Products →</a>"

        if any(w in m for w in ['order','orders','sale','sales','purchase']):
            try:
                from orders.models import Order
                from django.db.models import Sum
                total = Order.objects.count()
                pending = Order.objects.filter(status='pending').count()
                rev = Order.objects.exclude(status='cancelled').aggregate(t=Sum('total'))['t'] or 0
                return f"Total {total} orders, {pending} pending. Revenue: ₹{float(rev):.0f}. 📊 <a href='/admin-panel/orders/' style='color:#f5a623;font-weight:700;'>View Orders →</a>"
            except Exception:
                return "View all orders at <a href='/admin-panel/orders/' style='color:#f5a623;font-weight:700;'>Orders Panel</a> 📦"

        if any(w in m for w in ['revenue','earning','income','money','profit','chart']):
            try:
                from orders.models import Order
                from django.db.models import Sum
                rev = Order.objects.exclude(status='cancelled').aggregate(t=Sum('total'))['t'] or 0
                return f"Total revenue is ₹{float(rev):.0f}. 📈 <a href='/admin-panel/revenue/' style='color:#f5a623;font-weight:700;'>View Revenue Chart →</a>"
            except Exception:
                return "Check revenue at <a href='/admin-panel/revenue/' style='color:#f5a623;font-weight:700;'>Revenue Page</a> 📈"

        if any(w in m for w in ['categor','category','categories']):
            cats = ', '.join(list(Category.objects.values_list('name', flat=True)))
            return f"Categories: {cats or 'None yet'}. <a href='/admin-panel/categories/' style='color:#f5a623;font-weight:700;'>Manage Categories →</a> 🏷️"

        return f"Hi Admin{hi} 🛡️ You can manage: <a href='/admin-panel/sellers/' style='color:#f5a623;'>Sellers</a>, <a href='/admin-panel/customers/' style='color:#f5a623;'>Customers</a>, <a href='/admin-panel/products/' style='color:#f5a623;'>Products</a>, <a href='/admin-panel/orders/' style='color:#f5a623;'>Orders</a>, <a href='/admin-panel/revenue/' style='color:#f5a623;'>Revenue</a>. What do you need?"

    # ── SELLER ─────────────────────────────────────────────────
    elif role == 'seller':
        if any(w in m for w in ['product','products','add product','my product','listing']):
            try:
                from accounts.models import Seller
                s = Seller.objects.get(id=request.session['user_id'])
                count = Product.objects.filter(seller=s).count()
                return f"You have {count} products listed. <a href='/seller/products/' style='color:#f5a623;font-weight:700;'>Manage →</a> or <a href='/seller/product/add/' style='color:#f5a623;font-weight:700;'>Add New →</a> 📦"
            except Exception:
                return "Manage at <a href='/seller/products/' style='color:#f5a623;font-weight:700;'>My Products →</a> 📦"

        if any(w in m for w in ['order','orders','my order','sale']):
            return "Check your orders at <a href='/seller/orders/' style='color:#f5a623;font-weight:700;'>My Orders →</a> You can update status there. 📋"

        if any(w in m for w in ['discount','coupon','promo','code','offer']):
            return "Create discount codes at <a href='/seller/discounts/' style='color:#f5a623;font-weight:700;'>Discounts →</a> Set percentage or flat discounts! 🎁"

        if any(w in m for w in ['earning','revenue','income','money','profit','total']):
            try:
                from accounts.models import Seller
                from orders.models import Order, OrderItem
                from django.db.models import Sum
                s = Seller.objects.get(id=request.session['user_id'])
                order_ids = OrderItem.objects.filter(product__seller=s).values_list('order_id', flat=True).distinct()
                rev = Order.objects.filter(id__in=order_ids).exclude(status='cancelled').aggregate(t=Sum('total'))['t'] or 0
                return f"Your total earnings: ₹{float(rev):.0f}. 💰 <a href='/seller/dashboard/' style='color:#f5a623;font-weight:700;'>View Dashboard →</a>"
            except Exception:
                return "Check earnings on your <a href='/seller/dashboard/' style='color:#f5a623;font-weight:700;'>Dashboard →</a> 💰"

        if any(w in m for w in ['dashboard','home','panel','stats']):
            return f"Your Seller Panel: <a href='/seller/dashboard/' style='color:#f5a623;'>Dashboard</a> | <a href='/seller/products/' style='color:#f5a623;'>Products</a> | <a href='/seller/orders/' style='color:#f5a623;'>Orders</a> 🏪"

        if any(w in m for w in ['profile','account','password','name','phone']):
            return f"Edit your profile at <a href='/accounts/seller-profile/' style='color:#f5a623;font-weight:700;'>My Profile →</a> 👤"

        return f"Hi Seller{hi} 🏪 I can help with <a href='/seller/products/' style='color:#f5a623;'>products</a>, <a href='/seller/orders/' style='color:#f5a623;'>orders</a>, <a href='/seller/discounts/' style='color:#f5a623;'>discounts</a>, or earnings. What do you need?"

    # ── CUSTOMER / GUEST ────────────────────────────────────────
    else:
        if any(w in m for w in ['order','orders','my order','track','tracking','delivery status','where is']):
            if role == 'customer':
                return f"Track your orders here 👉 <a href='/cart/my-orders/' style='color:#f5a623;font-weight:700;'>My Orders →</a> Need help with a specific order?"
            return "Please <a href='/accounts/login/' style='color:#f5a623;font-weight:700;'>login</a> first to view your orders. 😊"

        if any(w in m for w in ['cart','bag','basket','checkout']):
            return "Your cart 🛒 <a href='/cart/' style='color:#f5a623;font-weight:700;'>View Cart →</a> Add products and checkout when ready!"

        if any(w in m for w in ['ship','delivery','shipping','free ship','deliver','when']):
            return "🚚 FREE shipping above ₹499! Below that, just ₹49 flat. We deliver all across India!"

        if any(w in m for w in ['return','refund','cancel','exchange']):
            return "To cancel an order, go to <a href='/cart/my-orders/' style='color:#f5a623;font-weight:700;'>My Orders</a> and click Cancel (only pending/confirmed orders). For refunds, contact support@shopease.com 📞"

        if any(w in m for w in ['payment','pay','cod','online','upi','card','wallet','razorpay','net banking','netbanking']):
            return "We support two payment methods: 💵 <strong>Cash on Delivery (COD)</strong> — pay at your door, and 💳 <strong>Online Payment via Razorpay</strong> — UPI, Cards, Net Banking, Wallets (256-bit SSL secured). Choose at checkout! 🔐"

        if any(w in m for w in ['discount','coupon','promo','offer','code','deal']):
            return "🎁 Got a discount code? Enter it in your cart before checkout! Codes are from our sellers."

        if any(w in m for w in ['product','shop','buy','browse','find','search','looking']):
            cats = ', '.join(list(Category.objects.values_list('name', flat=True)[:4]))
            return f"Browse our products at <a href='/products/' style='color:#f5a623;font-weight:700;'>Shop Now →</a> Categories: {cats or 'many options'}! 🛍️"

        if any(w in m for w in ['wishlist','saved','favourite','fav','heart']):
            return f"Your saved items 💝 <a href='/products/wishlist/' style='color:#f5a623;font-weight:700;'>My Wishlist →</a> Use ❤️ on any product to save it!"

        if any(w in m for w in ['contact','support','help','phone','email','call','reach']):
            return "📞 +91 96879 07055 | ✉️ support@shopease.com — We're happy to help!"

        if any(w in m for w in ['gst','tax','vat','charges']):
            return "5% GST is applied at checkout. No hidden charges! Everything is shown before you pay. 😊"

        if any(w in m for w in ['profile','account','password','edit','update']):
            if role == 'customer':
                return f"Update your profile at <a href='/accounts/profile/' style='color:#f5a623;font-weight:700;'>Edit Profile →</a> 👤"
            return "Please <a href='/accounts/login/' style='color:#f5a623;font-weight:700;'>login</a> to manage your account!"

        if any(w in m for w in ['register','signup','sign up','create account','new account']):
            return "Register at <a href='/accounts/register/' style='color:#f5a623;font-weight:700;'>Create Account →</a> It's free and takes 30 seconds! 🚀"

        if any(w in m for w in ['login','log in','sign in','signin']):
            return "Login at <a href='/accounts/login/' style='color:#f5a623;font-weight:700;'>Login →</a> 🔐"

        if any(w in m for w in ['price','cost','cheap','expensive','affordable','budget']):
            return f"We have products for every budget! Browse at <a href='/products/' style='color:#f5a623;font-weight:700;'>Shop →</a> and use the sort feature to filter by price. 💰"

        if any(w in m for w in ['category','categories','type','kind']):
            cats = ', '.join(list(Category.objects.values_list('name', flat=True)))
            return f"Our categories: {cats or 'check the shop'}. Browse at <a href='/products/' style='color:#f5a623;font-weight:700;'>Shop →</a> 🏷️"

        return random.choice([
            f"Hmm, not sure about that{hi} 🤔 Try asking about products, orders, shipping, or payments!",
            f"I didn't quite get that! 😊 You can ask me about orders, products, delivery, discounts, or any ShopEase help.",
            f"Good question{hi} For anything specific, try <a href='/products/' style='color:#f5a623;'>browsing the shop</a> or contact us at support@shopease.com 😊",
        ])


def _save_log(request, user_msg, bot_reply):
    try:
        from .models import ChatLog
        ChatLog.objects.create(
            session_key=request.session.session_key or 'anon',
            user_role=request.session.get('user_role'),
            user_id=request.session.get('user_id'),
            user_message=user_msg,
            bot_response=bot_reply,
        )
    except Exception:
        pass