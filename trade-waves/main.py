import urllib, http.client
import time
import json
# эти модули нужны для генерации подписи API
import hmac, hashlib
import matplotlib.pyplot as plot

f = open('/home/exmo_key.dat')

API_KEY = f.readline(42)
API_SECRET = (f.readline(42)).encode()

f.close()

CURRENCY_1 = 'BTC'
CURRENCY_2 = 'USD'

CURRENCY_1_MIN_QUANTITY = 0.001 # https://api.exmo.com/v1/pair_settings/
STOCK_FEE           = 0.002     # Комиссия, которую берет биржа (0.002 = 0.2%)

ORDER_LIFE_TIME     = 5         # через сколько минут отменять неисполненный ордер на покупку CURRENCY_1
AVG_PRICE_PERIOD    = 180       # За какой период брать среднюю цену
SLEEP_TIME          = 1         # Время ожидания для получения новых цен
CAN_SPEND           = 8       # Сколько тратить CURRENCY_2 каждый раз при покупке CURRENCY_1
PROFIT_MARKUP       = 0.002     # Какой навар нужен с каждой сделки? (0.001 = 0.1%)
PRICE_PERCENT       = 0.2       # Коэффициент для формирования цены
DEALS_NUM           = 5         # Количество сделок после которого завершить работу
LINREG_LIM          = -0.01     #
LINREG_PU_LIM       = 1       #
LINREG_PD_LIM       = -0.5      #

DEBUG               = False     # True - выводить отладочную информацию, False - писать как можно меньше
STOCK_TIME_OFFSET   = 0         # Если расходится время биржи с текущим

# базовые настройки
API_URL = 'api.exmo.com'
API_VERSION = 'v1'

# Свой класс исключений
class ScriptError(Exception):
    pass
class ScriptQuitCondition(Exception):
    pass

CURRENT_PAIR = CURRENCY_1 + '_' + CURRENCY_2

#====================================================================================================================#
#====================================================================================================================#

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

#====================================================================================================================#

# Количество времени которое прошло с момента date в минутах
def time_passed_min(date):
    return ((time.time() + STOCK_TIME_OFFSET*60*60 - date) / 60)

#====================================================================================================================#

def find_prices(prices):

    f_price_inf = open('price_inf.log', 'a')
    deals = call_api('trades', pair=CURRENT_PAIR)

    if len(prices) == 0:
        f_price_inf.write("----------------------------------------init prices list----------------------------------------\n")
        # print('init prices list')

        # Формирование первоначального списка цен
        for deal in deals[CURRENT_PAIR]:
            time_passed = (time.time() + STOCK_TIME_OFFSET*60*60 - int(deal['date'])) / 60
            # print('{0:10.5f} {1:10.3f} {2:10}'.format(time_passed, float(deal['price']), deal['type']))
            if time_passed <= AVG_PRICE_PERIOD + 5:
                prices.append([float(deal['price']), int(deal['date']) ]) # ------[0] - price------------------[1] - date------

        # Добавление в список цен пока последняя не будет старше заданного значения
        while (time.time() + STOCK_TIME_OFFSET*60*60 - prices[len(prices) - 1][1]) / 60 < AVG_PRICE_PERIOD:

            f_price_inf.write('{0:10.5f}: sleep {1:3.1f} min | price_arr_len = {2:6d}\n'.format((time.time() - prices[len(prices) - 1][1]) / 60, SLEEP_TIME, len(prices)))
            print('{0:10.5f}: sleep {1:3.1f} min | price_arr_len = {2:6d}'.format((time.time() - prices[len(prices) - 1][1]) / 60, SLEEP_TIME, len(prices)))

            time.sleep(SLEEP_TIME * 60)

            deals = call_api('trades', pair=CURRENT_PAIR)

            for deal in deals[CURRENT_PAIR]:
                time_passed = (time.time() + STOCK_TIME_OFFSET*60*60 - int(deal['date'])) / 60
                if time_passed < SLEEP_TIME:
                    prices.insert(0, [float(deal['price']), int(deal['date'])])

        f_price_inf.write("-------------------------------------correcting prices list-------------------------------------\n")
    else:
        # print('correcting prices list')

        # Добавление новых цен в начало списка
        last_price = (int)(prices[0][1])
        count_add = 0
        for deal in deals[CURRENT_PAIR]:
            if ( time_passed_min(int(deal['date'])) ) < SLEEP_TIME * 2.5:
                count_add = count_add + 1
                prices.insert(0, [float(deal['price']), int(deal['date'])])
                f_price_inf.write('{1:10.5f} | {0:10.3f}\n'.format(float(deal['price']), (time.time() - int(deal['date'])) / 60))
            else:
                break

        # Удаление уже "неинтересных" цен
        count_old = 0
        while((time.time() + STOCK_TIME_OFFSET*60*60 - prices[len(prices) - 1][1]) / 60 > AVG_PRICE_PERIOD):
            count_old = count_old + 1
            prices.pop()

        f_price_inf.write('added:         {0:6d}\n'.format(count_add))
        f_price_inf.write('deleted old:   {0:6d}\n'.format(count_old))

    # Удаление сделок по одинаковой цене в одно и тоже время
    prev_time = prices[0][1]
    prev_pr = prices[0][0]
    i = 1
    count_del = 0
    while i < len(prices) - 1:
        if (prices[i][1] == prev_time) and (prev_pr == prices[i][0]):
            count_del = count_del + 1
            prices.pop(i)
        else:
            prev_time = prices[i][1]
            prev_pr = prices[i][0]
            i += 1

    f_price_inf.write('deleted same:  {0:6d}\n'.format(count_del))
    f_price_inf.write('price_arr_len: {0:6d}\n'.format(len(prices)))

    f_price_inf.write("------------------------------------------------------------------------------------------------\n")

    f_price_inf.close();

#====================================================================================================================#

def print_prices(prices):

    f_price = open('price_arr.log', 'w')

    f_price.write("----------------------------------------PRICES ARRAY----------------------------------------\n")
    for e in prices:
        f_price.write('{1:10.5f} {0:10.3f}\n'.format(e[0], (time.time() - e[1]) / 60))
    f_price.write("--------------------------------------------------------------------------------------------\n")

    f_price.close();

#====================================================================================================================#

# Метод формирования цены закупки основанный на анализе предыдущих цен
def buy_price(prices):

    # Поиск максимальных и минимальных цен
    max_el = prices[0][0]
    min_el = prices[0][0]
    for e in prices:
        if max_el < e[0]:
            max_el = e[0]
        if min_el > e[0]:
            min_el = e[0]

    # Y = ((max_el - min_el) * PRICE_PERCENT) + min_el

    a30, b30 = pr_linreg(prices, 30, True)
    a, b = pr_linreg(prices, AVG_PRICE_PERIOD, False)

    if (a > LINREG_LIM):
        Yt = ((max_el - min_el) * PRICE_PERCENT) + min_el
    else:
        Yt = 0

    f_log = open('buy_pr.log', 'a')

    if (a30 < LINREG_PD_LIM):
        Yt = 0
        f_log.write("!!!!!!!!!!GABELLA DOWN!!!!!!!!!!\n")

    if (a30 > LINREG_PU_LIM):
        f_log.write("!!!!!!!!!!GABELLA UP!!!!!!!!!!\n")

    f_log.write('a30, b30:\t{0:10.5f}, {1:10.5f}\n'.format(a30, b30))
    f_log.write('a, b:\t\t{0:10.5f}, {1:10.5f}\n\n'.format(a, b))
    f_log.write('max:\t\t\t{0:10.5f}\nmin:\t\t\t{1:10.5f}\nprice:\t\t\t{2:10.5f}\n'.format(max_el, min_el, Yt))
    f_log.write("----------\n")

    f_log.close()

    return Yt

#====================================================================================================================#

# Вычисление линейной регрессии
def linreg(X, Y):
    """
    return a,b in solution to y = ax + b such that root mean square distance between trend line and original points is minimized
    """
    N = len(X)
    Sx = Sy = Sxx = Syy = Sxy = 0.0
    for x, y in zip(X, Y):
        Sx = Sx + x
        Sy = Sy + y
        Sxx = Sxx + x*x
        Syy = Syy + y*y
        Sxy = Sxy + x*y
    det = Sxx * N - Sx * Sx
    return (Sxy * N - Sy * Sx)/det, (Sxx * Sy - Sx * Sxy)/det

#====================================================================================================================#

# Вычисление тренда для определенного промежутка цен
def pr_linreg(prices, timeframe, gabella):

    pr_list = []
    prnum_g = 50

    for price in prices:
        if time_passed_min(price[1]) <= timeframe:
            pr_list.append(price[0])

    if gabella:
        prev_pr = pr_list[0]
        i = 1
        while i < len(pr_list):
            if (prev_pr == pr_list[i]):
                pr_list.pop(i)
            else:
                prev_pr = pr_list[i]
                i += 1

        t1 = pr_list[0:prnum_g]
        t2 = pr_list[(len(pr_list) - prnum_g):len(pr_list)]
        pr_list = []

        for e in t1:
            pr_list.append(e)
        for e in t2:
            pr_list.append(e)

    a,b = linreg(range(len(pr_list)), pr_list)

    # plot_linreg(a, b, pr_list)

    return a, b

#====================================================================================================================#

# Построить линейную регрессию
def plot_linreg(a, b, pr_list):

    xlr = []
    ylr = []

    xlr = list(range(len(pr_list)))
    for e in xlr:
        ylr.append(a * e + b)

    plot.plot(xlr, ylr)
    plot.plot(pr_list)
    plot.show()

#====================================================================================================================#

# Реализация алгоритма
def main_flow(prices_arr):

    # f_log = open('main_flow.log', 'a')
    retval = 0

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
                retval = 1
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
                    try:
                        my_need_price = buy_price(prices_arr)
                        if (my_need_price != 0):
                            my_amount = CAN_SPEND / my_need_price

                            print('buy', my_amount, my_need_price)

                            # Допускается ли покупка такого кол-ва валюты (т.е. не нарушается минимальная сумма сделки)
                            if my_amount >= CURRENCY_1_MIN_QUANTITY:
                                # retval = 1
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

    # f_log.close()

    return retval

#====================================================================================================================#

def main():
    pr_array = []

    f = open('buy_pr.log', 'w')
    f.close()

    f = open('price_inf.log', 'w')
    f.close()

    find_prices(pr_array)
    time_pr = time.time()
    count = 0
    start = time.time()

    while(count < DEALS_NUM):

        if(main_flow(pr_array)):
            count = count + 1
        time.sleep(5)

        if (time.time() - time_pr) / 60 > 3 * SLEEP_TIME:
            find_prices(pr_array)
            time_pr = time.time()

    print('TIME:\t{0:10.5f}\n'.format((time.time() - start) / 3600))

#====================================================================================================================#
#====================================================================================================================#

main()
