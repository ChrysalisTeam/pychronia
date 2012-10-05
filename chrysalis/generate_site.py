
import os, sys

assert not os.system(r"python C:\Python27\Scripts\rst2html.py --no-doc-title --template=template.html website.rst  index.html")

'''
with open("website.html") as f:
	html_data = f.read()
	
with open("template.html") as f:
	template_data = f.read()
	
result = template_data.replace("{content}", html_data)

with open("index.html", "w") as f:
	f.write(result)'''
