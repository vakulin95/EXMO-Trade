import datetime

now = datetime.datetime.now()

print(now)

f = open('file.dat', 'a')

count = 1

f.write('{0:3d}\t- {1}\n'.format(count, datetime.datetime.now()))

f.close()

arr = []

for i in range(5):
    arr.append([i, 1])

for i in range(5, 10):
    arr.append([3, 2])

arr.append([3, 15])

for i in range(10, 15):
    arr.append([i, 3])

for e in arr:
    print(e[0], e[1])
print("\n")

max_el = arr[0][1]
min_el = arr[0][1]
for e in arr:
    if max_el < e[1]:
        max_el = e[1]
    if min_el > e[1]:
        min_el = e[1]

Y = ((max_el - min_el) * 0.05) + min_el

print('max:{0:10.5f}\nmin:{1:10.5f}\nprice:{2:10.5f}'.format(max_el, min_el, Y))



# for e in arr:
#     print(e[0], e[1])
