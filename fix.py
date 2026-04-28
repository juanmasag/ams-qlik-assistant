f = open(r'src/grabador_corporativo.py', 'r', encoding='utf-8')
content = f.read()
f.close()

viejo = '        output_final   = os.path.join(_carpeta, f"{self.filename_base}.mp4"'
nuevo = '        output_final   = os.path.join(_carpeta, f"{self.filename_base}.mp4")'

if viejo in content:
    content = content.replace(viejo, nuevo)
    f = open(r'src/grabador_corporativo.py', 'w', encoding='utf-8')
    f.write(content)
    f.close()
    print("OK")
else:
    print("ERROR no encontrado")