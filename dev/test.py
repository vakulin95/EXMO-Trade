f = open('/home/artyom/Документы/exmo_key.dat')

API_KEY = f.readline(42)
API_SECRET = (f.readline(42)).encode()

print(API_KEY)
