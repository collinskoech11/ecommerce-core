from django.db.models import Q
from django.utils import timezone

from accounts.models import User
from orders.models import OrderItem, Order
from products.models import Item, Variation


def add_to_cart(user: User, item: Item, variations):
    """
    Add OrderItems to Order(cart)
    """

    # order item queryset, check for items already in the cart
    order_item_qs = OrderItem.objects.filter(
        item=item,
        user=user,
        ordered=False
    )
    if variations:
        for v in variations:
            order_item_qs = order_item_qs.filter(
                Q(item_variations__exact=v)
            )

    # if item is in OrderItem, add quantity
    if order_item_qs.exists():
        order_item = order_item_qs.first()
        order_item.quantity += 1
        order_item.save()
    # else create item in OrderItem
    else:
        order_item = OrderItem.objects.create(
            item=item,
            user=user,
            ordered=False
        )
        order_item.item_variations.add(*variations)
        order_item.save()
    # check if there is an active order
    order_qs = Order.objects.filter(user=user, ordered=False)
    # add item to Order if there is an active order
    if order_qs.exists():
        order = order_qs[0]
        if not order.items.filter(item__id=order_item.id).exists():
            order.items.add(order_item)
            return True
    # create order & add item to Order otherwise
    else:
        ordered_date = timezone.now()
        order = Order.objects.create(
            user=user, ordered_date=ordered_date)
        order.items.add(order_item)
        return True


def reduce_order_item_quantity(user: User, item: Item, ):
    """
    Reduce order item quantity
    """

    # get Order
    order_qs = Order.objects.filter(
        user=user,
        ordered=False
    )
    if order_qs.exists():
        order = order_qs[0]
        # get OrderItem
        if order.items.filter(item__slug=item.slug).exists():
            order_item = OrderItem.objects.filter(
                item=item,
                user=user,
                ordered=False
            )[0]
            # if there are more than one, reduce quantity by one
            if order_item.quantity > 1:
                order_item.quantity -= 1
                order_item.save()
            # else delete it
            else:
                order.items.remove(order_item)
            return True
        else:
            raise Exception("This item was not in your cart")
    else:
        raise Exception("You do not have an active order")