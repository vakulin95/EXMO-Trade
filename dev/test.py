import time

f_log = open('print_out.log', 'w')


f_log.write("1")
f_log.write('1')
f_log.write('1')

time_p = time.time()
time.sleep(10)
print(time.time() - time_p)

t = 1

if(t):
    print("+")
else:
    print("-")
