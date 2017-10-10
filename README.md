# Exmo trader

Crypto bot on python3

## Сontent

- [dev]() - some scripts without real trading
- [trade-pump]() - simple trader without any analysis
- [trade-waves]() - app accumulates transaction prices

## Options

```Python
CURRENCY_1_MIN_QUANTITY = 0.001 # https://api.exmo.com/v1/pair_settings/

ORDER_LIFE_TIME = 3     # через сколько минут отменять неисполненный ордер на покупку CURRENCY_1
STOCK_FEE = 0.002       # Комиссия, которую берет биржа (0.002 = 0.2%)
AVG_PRICE_PERIOD = 240  # За какой период брать среднюю цену
SLEEP_TIME = 1          # Время ожидания для получения новых цен
CAN_SPEND = 10          # Сколько тратить CURRENCY_2 каждый раз при покупке CURRENCY_1
PROFIT_MARKUP = 0.003   # Какой навар нужен с каждой сделки? (0.001 = 0.1%)
DEBUG = False            # True - выводить отладочную информацию, False - писать как можно меньше
PRICE_PERCENT = 0.2    # Коэффициент для формирования цены

STOCK_TIME_OFFSET = 0 # Если расходится время биржи с текущим
```
