import os
from collections import defaultdict

from fastapi import Depends, HTTPException
from jose import JWTError, jwt
from slugify import slugify
from sqlalchemy.orm import Session

from shop import constants
from shop.auth import oauth2_scheme
from shop.database import SessionLocal, TestingSessionLocal
from shop.models import CartItem, Category, Item, ItemReview, NewsLetter, Order, OrderItem, Shop, ShopOrder, User
from shop.schemas import TokenData


# Dependency to get the database session
def get_db():
    if os.getenv("ENVIRONMENT") == "test":
        db = TestingSessionLocal()
        yield db
        db.close()
    else:
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()


def get_current_user(db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)) -> User:
    credentials_exception = HTTPException(
        status_code=401,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(
            token,
            constants.JWT_SECRET,
            algorithms=[constants.ALGORITHM],
            options={"verify_aud": False},
        )
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except JWTError:
        raise credentials_exception

    user = db.query(User).filter(
        User.id == token_data.username,
    )

    if user.first():
        active_user = user.filter(User.is_active == True).first()
        if active_user:
            return active_user
        raise HTTPException(status_code=401, detail="Please activate your account.")
    else:
        raise credentials_exception


def get_current_shop(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Shop:
    if current_user.role == "SHOP":
        shop = db.query(Shop).filter(Shop.user_id == current_user.id, Shop.is_approved == True).first()
        if shop:
            return shop
        else:
            raise HTTPException(status_code=403, detail="Your shop is not approved.")
    else:
        raise HTTPException(status_code=403, detail="Forbidden.")


def get_super_user(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.is_superuser:
        return current_user
    else:
        raise HTTPException(status_code=403, detail="Only Site Administrator can access this page.")


def check_user_email_or_username(db: Session, email: str, username: str):
    if email:
        existing_user = db.query(User).filter(User.email == email).first()
        if existing_user:
            raise HTTPException(status_code=409, detail="Email is already taken.")

    if username:
        existing_user = db.query(User).filter(User.username == username).first()
        if existing_user:
            raise HTTPException(status_code=409, detail="Username is already taken.")

    return existing_user


def delete_user_by_id(db: Session, user_id: int):
    existing_user = db.query(User).filter(User.id == user_id).first()
    if not existing_user:
        raise HTTPException(status_code=404, detail="User not found.")
    if existing_user:
        db.delete(existing_user)
        db.commit()
    return existing_user


def get_user_by_id(db: Session, user_id: int):
    existing_user = db.query(User).filter(User.id == user_id).first()
    if not existing_user:
        raise HTTPException(status_code=404, detail="User not found.")
    return existing_user


def get_user_by_email(db: Session, email: str):
    existing_user = db.query(User).filter(User.email == email).first()
    if not existing_user:
        raise HTTPException(status_code=404, detail="User not found.")
    return existing_user


def check_free_username(db: Session, username: str):
    existing_user = db.query(User).filter(User.username == username).first()
    if existing_user:
        raise HTTPException(status_code=409, detail="Username is already taken.")

    return existing_user


def get_shop_by_slug(db: Session, shop_slug: str):
    existing_shop = db.query(Shop).filter(Shop.slug == shop_slug).first()
    if not existing_shop:
        raise HTTPException(status_code=404, detail="Shop not found.")
    return existing_shop


def check_free_shop_name(db: Session, shop_name: str):
    existing_shop = db.query(Shop).filter(Shop.shop_name == shop_name).first()
    if existing_shop:
        raise HTTPException(status_code=409, detail="Shop name is already taken.")

    return existing_shop


def generate_unique_category_slug(db: Session, shop_name: str, category_name: str):
    unique_slug = f"{slugify(shop_name)}-{slugify(category_name)}"
    counter = 1

    while db.query(Category).filter(Category.slug == unique_slug).first():
        unique_slug = f"{unique_slug}-{counter}"
        counter += 1

    return unique_slug


def generate_unique_shop_slug(db: Session, shop_name: str):
    counter = 1
    unique_slug = slugify(shop_name)

    while db.query(Shop).filter(Shop.slug == unique_slug).first():
        unique_slug = f"{unique_slug}-{counter}"
        counter += 1

    return unique_slug


def check_free_category_name(db: Session, shop_id: int, category_name: str):
    existing_category = db.query(Category).filter(Category.shop_id == shop_id, Category.name == category_name).first()
    if existing_category:
        raise HTTPException(status_code=409, detail=f"You already have category with the name '{category_name}'.")
    return existing_category


def get_category_by_slug_and_shop_id(db: Session, shop_id: int, category_slug: str):
    existing_category = db.query(Category).filter(Category.shop_id == shop_id, Category.slug == category_slug).first()
    if not existing_category:
        raise HTTPException(status_code=404, detail="Category not found.")
    return existing_category


def get_category_by_slug(db: Session, category_slug: str):
    existing_category = db.query(Category).filter(Category.slug == category_slug).first()
    if not existing_category:
        raise HTTPException(status_code=404, detail="Category not found.")
    return existing_category


def generate_unique_item_slug(db: Session, shop_name: str, item_name: str):
    unique_slug = f"{slugify(shop_name)}-{slugify(item_name)}"
    counter = 1

    while db.query(Item).filter(Item.slug == unique_slug).first():
        unique_slug = f"{unique_slug}-{counter}"
        counter += 1

    return unique_slug


def check_free_item_name(db: Session, shop_id: int, item_name: str):
    existing_item = db.query(Item).filter(Item.shop_id == shop_id, Item.name == item_name).first()
    if existing_item:
        raise HTTPException(status_code=409, detail=f"You already have item with the name '{item_name}'.")
    return existing_item


# TODO for better understanding consider add one more query to check
#  if category with the given slug exists in general and than check the shop owner
def get_item_by_slug_for_shop(db: Session, shop_id: int, item_slug: str):
    existing_item = db.query(Item).filter(Item.shop_id == shop_id, Item.slug == item_slug).first()
    if not existing_item:
        raise HTTPException(status_code=404, detail="Item not found.")
    return existing_item


def get_item_by_slug(db: Session, item_slug: str):
    existing_item = db.query(Item).filter(Item.slug == item_slug).first()
    if not existing_item:
        raise HTTPException(status_code=404, detail="Item not found.")
    return existing_item


def check_item_owner(db: Session, shop_id: int, item_slug: str):
    existing_item = (
        db.query(Item)
        .filter(
            Item.shop_id == shop_id,
            Item.slug == item_slug,
        )
        .first()
    )
    if not existing_item:
        raise HTTPException(status_code=403, detail="Forbidden.")
    return existing_item


def get_cart_item(db: Session, user_id: int, item_id: int):
    existing_cart_item = (
        db.query(CartItem)
        .join(CartItem.item)
        .filter(
            CartItem.user_id == user_id,
            Item.id == item_id,
        )
        .first()
    )
    return existing_cart_item


def get_cart_items(db: Session, user_id: int):
    existing_cart_items = (
        db.query(CartItem)
        .filter(
            CartItem.user_id == user_id,
        )
        .all()
    )
    if not existing_cart_items:
        raise HTTPException(status_code=409, detail="Cart is empty.")
    return existing_cart_items


def get_orders(db: Session, user_id: int):
    existing_orders = db.query(Order).filter(Order.user_id == user_id, Order.billing_status == True).all()
    if not existing_orders:
        raise HTTPException(status_code=409, detail="You have no orders yet.")
    return existing_orders


def get_order_by_order_id(db: Session, order_id: int):
    existing_order = (
        db.query(Order)
        .filter(
            Order.id == order_id,
        )
        .first()
    )
    if not existing_order:
        raise HTTPException(status_code=404, detail="Order not found.")
    return existing_order


def get_order_by_order_key(db: Session, order_key: str):
    existing_order = db.query(Order).filter(Order.order_key == order_key).first()
    if not existing_order:
        raise HTTPException(status_code=404, detail="Order not found.")
    return existing_order


def get_shop_orders(db: Session, shop_id: int):
    existing_orders = db.query(ShopOrder).filter(ShopOrder.shop_id == shop_id, ShopOrder.billing_status == True).all()
    if not existing_orders:
        raise HTTPException(status_code=409, detail="You have no orders yet.")
    return existing_orders


def get_shop_order_by_order_id(db: Session, order_id: int, shop_id: int):
    existing_order = (
        db.query(ShopOrder)
        .filter(
            ShopOrder.shop_id == shop_id,
            ShopOrder.id == order_id,
            ShopOrder.billing_status == True,
        )
        .first()
    )
    if not existing_order:
        raise HTTPException(status_code=404, detail="Order not found.")
    return existing_order


def get_shop_orders_by_user_id_for_shop(db: Session, user_id: int, shop_id: int):
    existing_orders = (
        db.query(ShopOrder)
        .filter(
            ShopOrder.shop_id == shop_id,
            ShopOrder.user_id == user_id,
            ShopOrder.billing_status == True,
        )
        .all()
    )
    if not existing_orders:
        raise HTTPException(status_code=409, detail="User has no orders in your shop.")
    return existing_orders


def get_all_users_ordered_in_shop(db: Session, shop_id: int):
    shop_orders = (
        db.query(ShopOrder)
        .filter(
            ShopOrder.shop_id == shop_id,
            ShopOrder.billing_status == True,
        )
        .all()
    )
    users_per_shop = set()
    for order in shop_orders:
        user = db.query(User).filter(User.id == order.user_id).first()
        users_per_shop.add(user)
    if not users_per_shop:
        raise HTTPException(status_code=409, detail="No users have ordered in your shop.")
    return users_per_shop


def get_stats_for_each_item(db: Session, shop_id: int):
    items_per_shop = (
        db.query(Item)
        .filter(
            Item.shop_id == shop_id,
        )
        .all()
    )
    items_ids = [item.id for item in items_per_shop]

    item_price_quantity_dict = defaultdict(dict)

    order_items = (
        db.query(OrderItem)
        .filter(
            OrderItem.item_id.in_(items_ids),
        )
        .all()
    )

    for order_item in order_items:
        item = db.query(Item).filter(Item.id == order_item.item_id).first()
        if order_item.item_id not in item_price_quantity_dict:
            item_price_quantity_dict[order_item.item_id]["price"] = order_item.price
            item_price_quantity_dict[order_item.item_id]["quantity"] = order_item.quantity
        else:
            item_price_quantity_dict[order_item.item_id]["price"] += order_item.price
            item_price_quantity_dict[order_item.item_id]["quantity"] += order_item.quantity

        item_price_quantity_dict[order_item.item_id]["wish_list_count"] = len(item.users)
        item_price_quantity_dict[order_item.item_id]["reviews_count"] = len(item.reviews)
        item_price_quantity_dict[order_item.item_id]["average_rating"] = item.average_rating

    if not item_price_quantity_dict:
        raise HTTPException(status_code=409, detail="No items have been sold in your shop.")

    return item_price_quantity_dict


def get_total_revenue_with_filtering(db: Session, shop_id: int, start_date: str, end_date: str):
    shop_orders = (
        db.query(ShopOrder)
        .filter(
            ShopOrder.shop_id == shop_id,
            ShopOrder.billing_status == True,
            ShopOrder.created_at.between(start_date, end_date),
        )
        .all()
    )

    total_revenue = 0
    for order in shop_orders:
        total_revenue += order.total_paid
    if not total_revenue:
        raise HTTPException(status_code=409, detail="You have no orders in your shop for the given period.")
    return {"Revenue": total_revenue}


def get_total_revenue(db: Session, shop_id: int):
    shop_orders = (
        db.query(ShopOrder)
        .filter(
            ShopOrder.shop_id == shop_id,
            ShopOrder.billing_status == True,
        )
        .all()
    )
    total_revenue = 0
    for order in shop_orders:
        total_revenue += order.total_paid
    if not total_revenue:
        raise HTTPException(status_code=409, detail="No orders have been made in your shop.")
    return {"Total revenue": total_revenue}


def check_if_email_already_signed_for_newsletter(db: Session, email: str):
    existing_email = db.query(NewsLetter).filter(NewsLetter.email == email, NewsLetter.is_active == True).first()
    if existing_email:
        raise HTTPException(status_code=409, detail="Email is already signed for newsletter.")

    return existing_email


def get_newsletter_by_id(db: Session, newsletter_id: int):
    existing_email = db.query(NewsLetter).filter(NewsLetter.id == newsletter_id).first()
    if not existing_email:
        raise HTTPException(status_code=404, detail="Email not found.")
    return existing_email


def check_if_user_bought_item(db: Session, user_id: int, item_id: int):
    existing_order = (
        db.query(OrderItem)
        .join(OrderItem.order)
        .filter(
            OrderItem.item_id == item_id,
            Order.user_id == user_id,
            Order.billing_status == True,
        )
        .first()
    )
    if not existing_order:
        raise HTTPException(status_code=409, detail="You can leave a review only if you bought this item.")
    return existing_order


def get_cart_item_by_id(db: Session, cart_item_id: int):
    existing_cart_item = db.query(CartItem).filter(CartItem.id == cart_item_id).first()
    if not existing_cart_item:
        raise HTTPException(status_code=404, detail="Cart item not found.")
    return existing_cart_item


def get_shop_order_by_id(db: Session, shop_order_id: int):
    existing_shop_order = db.query(ShopOrder).filter(ShopOrder.id == shop_order_id).first()
    if not existing_shop_order:
        raise HTTPException(status_code=404, detail="Shop order not found.")
    return existing_shop_order


def get_item_review_by_id(db: Session, item_review_id: int):
    existing_item_review = db.query(ItemReview).filter(ItemReview.id == item_review_id).first()
    if not existing_item_review:
        raise HTTPException(status_code=404, detail="Item review not found.")
    return existing_item_review
