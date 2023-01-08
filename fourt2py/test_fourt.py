import numpy as np

from fourt2py import fourt

a = np.zeros(15, dtype=complex)
a[1] = 1
a[3] = -1

print(fourt(a))
print(np.fft.fft(a))
