import urllib, http.client
import time
import json
# эти модули нужны для генерации подписи API
import hmac, hashlib

f = open('/home/exmo_key.dat')

API_KEY = f.readline(42)
API_SECRET = (f.readline(42)).encode()

f.close()

# Тонкая настройка
CURRENCY_1 = 'LTC'
CURRENCY_2 = 'USD'

CURRENCY_1_MIN_QUANTITY = 0.01 # минимальная сумма ставки - берется из https://api.exmo.com/v1/pair_settings/

ORDER_LIFE_TIME = 1 # через сколько минут отменять неисполненный ордер на покупку CURRENCY_1
STOCK_FEE = 0.002 # Комиссия, которую берет биржа (0.002 = 0.2%)
AVG_PRICE_PERIOD = 30 # За какой период брать среднюю цену
CAN_SPEND = 10 # Сколько тратить CURRENCY_2 каждый раз при покупке CURRENCY_1
PROFIT_MARKUP = 0.003 # Какой навар нужен с каждой сделки? (0.001 = 0.1%)
DEBUG = False # True - выводить отладочную информацию, False - писать как можно меньше

STOCK_TIME_OFFSET = 0 # Если расходится время биржи с текущим

# базовые настройки
API_URL = 'api.exmo.com'
API_VERSION = 'v1'

# Свой класс исключений
class ScriptError(Exception):
    pass
class ScriptQuitCondition(Exception):
    pass

CURRENT_PAIR = CURRENCY_1 + '_' + CURRENCY_2

# все обращения к API проходят через эту функцию
def call_api(api_method, http_method="POST", **kwargs):

    payload = {'nonce': int(round(time.time()*1000))}

    if kwargs:
        payload.update(kwargs)
    payload =  urllib.parse.urlencode(payload)

    H = hmac.new(key=API_SECRET, digestmod=hashlib.sha512)
    H.update(payload.encode('utf-8'))
    sign = H.hexdigest()

    headers = {"Content-type": "application/x-www-form-urlencoded",
           "Key":API_KEY,
           "Sign":sign}
    conn = http.client.HTTPSConnection(API_URL, timeout=60)
    conn.request(http_method, "/"+API_VERSION + "/" + api_method, payload, headers)
    response = conn.getresponse().read()

    conn.close()

    try:
        obj = json.loads(response.decode('utf-8'))

        if 'error' in obj and obj['error']:
            raise ScriptError(obj['error'])
        return obj
    except json.decoder.JSONDecodeError:
        raise ScriptError('Ошибка анализа возвращаемых данных, получена строка', response)

# Реализация алгоритма
def main_flow():

    try:
        # Получаем список активных ордеров
        try:
            opened_orders = call_api('user_open_orders')[CURRENCY_1 + '_' + CURRENCY_2]
        except KeyError:
            if DEBUG:
                print('Открытых ордеров нет')
            opened_orders = []

        sell_orders = []
        # Есть ли неисполненные ордера на продажу CURRENCY_1?
        for order in opened_orders:
            if order['type'] == 'sell':
                # Есть неисполненные ордера на продажу CURRENCY_1, выход
                raise ScriptQuitCondition('Выход, ждем пока не исполнятся/закроются все ордера на продажу (один ордер может быть разбит биржей на несколько и исполняться частями)')
            else:
                # Запоминаем ордера на покупку CURRENCY_1
                sell_orders.append(order)

        # Проверяем, есть ли открытые ордера на покупку CURRENCY_1
        if sell_orders: # открытые ордера есть
            for order in sell_orders:
                # Проверяем, есть ли частично исполненные
                if DEBUG:
                    print('Проверяем, что происходит с отложенным ордером', order['order_id'])
                try:
                    order_history = call_api('order_trades', order_id=order['order_id'])
                    # по ордеру уже есть частичное выполнение, выход
                    raise ScriptQuitCondition('Выход, продолжаем надеяться докупить валюту по тому курсу, по которому уже купили часть')
                except ScriptError as e:
                    if DEBUG:
                        print('Частично исполненных ордеров нет')

                    time_passed = time.time() + STOCK_TIME_OFFSET*60*60 - int(order['created'])

                    if time_passed > ORDER_LIFE_TIME * 60:
                        # Ордер уже давно висит, никому не нужен, отменяем
                        call_api('order_cancel', order_id=order['order_id'])
                        raise ScriptQuitCondition('Отменяем ордер -за ' + str(ORDER_LIFE_TIME) + ' минут не удалось купить '+ str(CURRENCY_1))
                    else:
                        raise ScriptQuitCondition('Выход, продолжаем надеяться купить валюту по указанному ранее курсу, со времени создания ордера прошло %s секунд' % str(time_passed))


        else: # Открытых ордеров нет
            balances = call_api('user_info')['balances']
            if float(balances[CURRENCY_1]) >= CURRENCY_1_MIN_QUANTITY: # Есть ли в наличии CURRENCY_1, которую можно продать?
                wanna_get = CAN_SPEND + CAN_SPEND * (STOCK_FEE + PROFIT_MARKUP)  # сколько хотим получить за наше кол-во
                print('sell', balances[CURRENCY_1], wanna_get, (wanna_get/float(balances[CURRENCY_1])))
                new_order = call_api(
                    'order_create',
                    pair=CURRENT_PAIR,
                    quantity = balances[CURRENCY_1],
                    price=wanna_get/float(balances[CURRENCY_1]),
                    type='sell'
                )
                print(new_order)
                if DEBUG:
                    print('Создан ордер на продажу', CURRENCY_1, new_order['order_id'])
            else:
                # CURRENCY_1 нет, надо докупить
                # Достаточно ли денег на балансе в валюте CURRENCY_2 (Баланс >= CAN_SPEND)
                if float(balances[CURRENCY_2]) >= CAN_SPEND:
                    deals = call_api('trades', pair=CURRENT_PAIR)
                    prices = []
                    for deal in deals[CURRENT_PAIR]:
                        time_passed = time.time() + STOCK_TIME_OFFSET*60*60 - int(deal['date'])
                        if time_passed < AVG_PRICE_PERIOD*60:
                            prices.append(float(deal['price']))
                    try:
                        avg_price = sum(prices)/len(prices)
                        # купить больше, потому что биржа потом заберет кусок
                        # my_need_price = avg_price - avg_price * (STOCK_FEE+PROFIT_MARKUP)
                        my_need_price = avg_price
                        my_amount = CAN_SPEND / my_need_price

                        print('buy', my_amount, my_need_price)

                        # Допускается ли покупка такого кол-ва валюты (т.е. не нарушается минимальная сумма сделки)
                        if my_amount >= CURRENCY_1_MIN_QUANTITY:
                            new_order = call_api(
                                'order_create',
                                pair=CURRENT_PAIR,
                                quantity = my_amount,
                                price=my_need_price,
                                type='buy'
                            )
                            print(new_order)
                            if DEBUG:
                                print('Создан ордер на покупку', new_order['order_id'])

                        else: # мы можем купить слишком мало на нашу сумму
                            ScriptQuitCondition('Выход, не хватает денег на создание ордера')
                    except ZeroDivisionError:
                        print('Не удается вычислить среднюю цену', prices)
                else:
                    raise ScriptQuitCondition('Выход, не хватает денег')

    except ScriptError as e:
        print(e)
    except ScriptQuitCondition as e:
        if DEBUG:
            print(e)
        pass
    except Exception as e:
        print("!!!!",e)

while(True):
    main_flow()
    time.sleep(1)
