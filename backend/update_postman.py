import json

# Leer el archivo principal
with open('../CRM-Backend-Collection.json', 'r', encoding='utf-8') as f:
    collection = json.load(f)

# Leer las nuevas secciones
with open('../products_activities_section.json', 'r', encoding='utf-8') as f:
    new_content = f.read()
    # Dividir en dos secciones
    sections = json.loads('[' + new_content + ']')

# Encontrar el índice de "Users & Roles"
users_index = None
for i, item in enumerate(collection['item']):
    if item['name'] == 'Users & Roles':
        users_index = i
        break

# Insertar las nuevas secciones antes de Users & Roles
if users_index is not None:
    collection['item'].insert(users_index, sections[0])  # Products
    collection['item'].insert(users_index + 1, sections[1])  # Activities
    print(f"[OK] Secciones agregadas antes de 'Users & Roles' (indice {users_index})")
else:
    # Si no se encuentra, agregar al final antes del último elemento
    collection['item'].insert(-1, sections[0])
    collection['item'].insert(-1, sections[1])
    print("[OK] Secciones agregadas al final de la coleccion")

# Actualizar la descripción
collection['info']['description'] += '\n- Catalogo de Productos y Listas de Precios\n- Actividades (Email, Phone Call, Task, Appointment)'

# Guardar el archivo actualizado
with open('../CRM-Backend-Collection.json', 'w', encoding='utf-8') as f:
    json.dump(collection, f, indent='\t', ensure_ascii=False)

print("[SUCCESS] Archivo CRM-Backend-Collection.json actualizado exitosamente")
print(f"[INFO] Total de secciones: {len(collection['item'])}")
