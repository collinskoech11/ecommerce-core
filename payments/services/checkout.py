from orders.models import Order
from payments.models import Payment, Transaction, TransactionPhone
from payments.services.payments import mobile_payments

# TODO: Transaction Atomic
# https://github.com/ljodal/djangocon-eu-2019/blob/master/orders/managers.py

def payment_failed(payment: Payment):
    """
    Save a failed payment
    :param payment: Payment object(Model)
    """
    payment.paid = False
    payment.waiting = False
    payment.cancelled = False
    payment.failed = True
    payment.save()


def transaction_failed(transaction: Transaction, error_message=None):
    """
    Save a failed Transaction
    :param transaction: Transaction object(model)
    :param error_message: Error message to be recorded
    """
    if error_message:
        if type(error_message) != str:
            try:
                error_message = str(error_message)
            except:
                error_message = None
    transaction.paid = False
    transaction.waiting = False
    transaction.failed = True
    transaction.error_message = error_message
    transaction.save()

    payment_failed(transaction.payment)


def save_transaction(transaction: Transaction, transaction_resp):
    """
    Save the transaction response as a Transaction object to the db
    :param transaction: Transaction model object
    :param transaction_resp: Transaction respsonse from africastalking API
    """

    if type(transaction_resp) == dict and transaction_resp['status']:

        if transaction_resp['description']:
            transaction.description = transaction_resp['description']

        if transaction_resp['transactionId']:
            transaction.transaction_id = transaction_resp['transactionId']

        if transaction_resp['providerChannel']:
            transaction.provider_channel = transaction_resp['providerChannel']

        if transaction_resp['status'] == 'InvalidRequest':
            transaction.save()
            transaction_failed(transaction=transaction,
                               error_message='InvalidRequest: The request could not be accepted as one of the fields '
                                             'was invalid. The description field will contain more information.')
            raise Exception('Transaction Failed: InvalidRequest')

        # Handle phone number not supported
        elif transaction_resp['status'] == 'NotSupported':
            # TODO: mark transaction phone number as invalid
            transaction.save()
            transaction_failed(transaction=transaction,
                               error_message='NotSupported: Checkout to the provided phone number is not supported.')
            raise Exception('Transaction Failed: NotSupported')
        # Handle unknown fail
        elif transaction_resp['status'] == 'Failed':
            transaction.save()
            transaction_failed(transaction=transaction, error_message='Failed')
            raise Exception('Transaction Failed: Failed')
        # Successful transaction. Awaiting confirmation from user
        elif transaction_resp['status'] == 'PendingConfirmation':
            transaction.save()
            return
        else:
            transaction.save()
            transaction_failed(transaction=transaction)
    else:
        transaction_failed(transaction=transaction, error_message='No response')
        raise Exception('Transaction Failed')


def make_payment(payment: Payment):
    """
    Process of making a payment. Creates Transaction.
    :param payment: Payment model object
    :return: save_transaction()
    """

    # new Transaction
    transaction = Transaction(payment=payment, waiting=True)
    transaction.save()
    response = None

    try:
        if payment.payment_method == 'M':

            # save transaction phone number
            transaction_phone = TransactionPhone(transaction=transaction,
                                                 phone_number=payment.order.billing_address.phone_number)
            transaction_phone.save()

            response = mobile_payments(
                phone_number=transaction_phone.phone_number,
                amount=payment.amount,
                transaction_id=str(transaction.id))

        elif payment.payment_method == 'C':
            # TODO
            raise Exception('Incorrect payment method')
        else:
            raise Exception('Incorrect payment method')
    except Exception as e:
        transaction_failed(transaction, e)
        raise Exception(e)
    else:
        return save_transaction(transaction=transaction, transaction_resp=response)


def checkout(order: Order, payment_method: str):
    """
    Pay for order.
    :param order: Order model object
    :param payment_method: Payment.payment_method
    :return: make_payment()
    """

    # Create Payment
    payment = Payment(order=order,
                      payment_method=payment_method,
                      amount=order.get_total(),
                      paid=False,
                      waiting=True,
                      cancelled=False,
                      failed=False)

    try:
        payment.save()
    except Exception as e:
        payment_failed(payment)
        raise Exception(e)
    else:
        return make_payment(payment)
