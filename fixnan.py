import re
with open('data/cache.json','r') as f:
    content = f.read()
fixed = re.sub(r'\bNaN\b', 'null', content)
with open('data/cache.json','w') as f:
    f.write(fixed)
print('Done')
