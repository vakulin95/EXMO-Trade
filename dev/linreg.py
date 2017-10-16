import numpy as np
import matplotlib.pyplot as plt

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

x = [5490, 5492, 5489, 5495, 5487,      5410, 5413, 5408, 5402, 5404]

a,b = linreg(range(len(x)),x)  # your x,y are switched from standard notation

xa = list(range(50))
ya = []
for e in xa:
    ya.append(a * e + b)

plt.plot(xa, ya)
plt.plot(x)
plt.show()

print(a, b)
