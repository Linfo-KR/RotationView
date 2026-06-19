import searoute as sr

def test():
    res = sr.searoute([-80.2, 25.8], [101.4, 3.0])
    lons = [c[0] for c in res['geometry']['coordinates']]
    print(min(lons), max(lons))
test()
