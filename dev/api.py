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
#
# # ключи API, которые предоставила exmo
# API_KEY = 'K-37c63e68e7a4896b44f0768cf6d1d08c187cc0ab'
# # обратите внимание, что добавлена 'b' перед строкой
# API_SECRET = b'S-7eed55da942f4b9666e9fde42ea4e409fbb7cfc6'

# Тонкая настройка
CURRENCY_1 = 'LTC'
CURRENCY_2 = 'USD'

CURRENCY_1_MIN_QUANTITY = 0.01 # минимальная сумма ставки - берется из https://api.exmo.com/v1/pair_settings/

ORDER_LIFE_TIME = 3     # через сколько минут отменять неисполненный ордер на покупку CURRENCY_1
STOCK_FEE = 0.002       # Комиссия, которую берет биржа (0.002 = 0.2%)
AVG_PRICE_PERIOD = 20   # За какой период брать среднюю цену
SLEEP_TIME = 0.1          # Время ожидания для получения новых цен
CAN_SPEND = 5           # Сколько тратить CURRENCY_2 каждый раз при покупке CURRENCY_1
PROFIT_MARKUP = 0.001   # Какой навар нужен с каждой сделки? (0.001 = 0.1%)
DEBUG = True            # True - выводить отладочную информацию, False - писать как можно меньше
PRICE_PERCENT = 0.2    # Коэффициент для формирования цены
DEALS_NUM  =10

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
                if int(deal['date']) > last_price:
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

# Метод формирования цены закупки основанный только на анализе предыдущих цен
def buy_price(prices):

    # Поиск максимальных и минимальных цен
    max_el = prices[0][0]
    min_el = prices[0][0]
    for e in prices:
        if max_el < e[0]:
            max_el = e[0]
        if min_el > e[0]:
            min_el = e[0]

    Y = ((max_el - min_el) * PRICE_PERCENT) + min_el

    a30, b30 = pr_linreg(prices, 5, True)
    # a60, b60 = pr_linreg(prices, 60, False)
    a, b = pr_linreg(prices, AVG_PRICE_PERIOD, False)

    f_log = open('buy_pr.log', 'a')

    f_log.write('a30, b30:\t{0:10.5f}, {1:10.5f}\n'.format(a30, b30))
    f_log.write('a, b:\t\t{0:10.5f}, {1:10.5f}\n\n'.format(a, b))
    f_log.write('max:\t\t{0:10.5f}\nmin:\t\t{1:10.5f}\nprice:\t\t{2:10.5f}\n'.format(max_el, min_el, Y))
    f_log.write("----------\n")

    f_log.close()
    return Y

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

def time_passed(date):
    return ((time.time() + STOCK_TIME_OFFSET*60*60 - date) / 60)

def pr_linreg(prices, timeframe, gabella):

    pr_list = []

    for price in prices:
        if time_passed(price[1]) <= timeframe:
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

    a,b = linreg(range(len(pr_list)), pr_list)

    return a, b

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
#====================================================================================================================#

def main():
    pr_array = []
    find_prices(pr_array)
    print("Price list compleete")
    time_pr = time.time()
    count = 0
    start = time.time()

    while(count < DEALS_NUM):

        if (time.time() - time_pr) / 60 > SLEEP_TIME:
            print("Sleep")
            find_prices(pr_array)
            buy_price(pr_array)
            time_pr = time.time()
            count = count + 1

    print('TIME:\t{0:10.5f}\n'.format((time.time() - start) / 3600))

#====================================================================================================================#
#====================================================================================================================#

main()
