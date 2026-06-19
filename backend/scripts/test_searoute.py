import searoute as sr
import json

origin = [139.638, 35.4437] # Yokohama
dest = [-76.2858, 36.8507] # Norfolk

res = sr.searoute(origin, dest)
coords = res['geometry']['coordinates']
with open('searoute_test.txt', 'w') as f:
    for c in coords:
        f.write(f"{c[0]}, {c[1]}\n")
print(f"Total points: {len(coords)}")
print(f"First 5: {coords[:5]}")
print(f"Last 5: {coords[-5:]}")
