import random

hits = 0
total = 10000
for i in range(total):
    x = random.random()
    y = random.random()
    if x * x + y * y <= 1.0:
        hits += 1
pi = 4.0 * hits / total
print(pi)
