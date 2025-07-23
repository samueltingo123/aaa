import os
import json
import pyodbc
from flask import Flask, render_template, request, jsonify
import google.generativeai as genai
import re
from datetime import datetime, timedelta
import logging
from flask_cors import CORS
from difflib import SequenceMatcher

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

genai.configure(api_key="AIzaSyD3VA8JfB8KM8bwREYeLGuXONw-zHbUmrQ")
app = Flask(__name__)

CORS(app)  

DB_CONFIG = {
    "server": "45.4.136.13",
    "database": "Monica_9",
    "username": "Samuel",
    "password": "321.cba"
}

SINONIMOS_PRODUCTOS = {
    'cerveza': ['cervezas', 'birra', 'birras', 'beer','guaro'],
    'refresco': ['refrescos', 'gaseosa', 'gaseosas', 'soda', 'sodas'],
    'agua': ['aguas', 'water'],
    'leche': ['leches', 'milk'],
    'arroz': ['arroces', 'rice'],
    'pan': ['panes', 'bread'],
    'michelob': ['michelob ultra', 'michelob light'],
    'corona': ['corona extra', 'corona light', 'coronas'],
    'pepsi': ['pepsi cola', 'pepsi-cola', 'pepsis'],
    'coca': ['coca cola', 'coca-cola', 'coke', 'cocas'],
    'sprite': ['sprite light', 'sprite zero', 'sprites'],
    'fanta': ['fanta naranja', 'fanta orange', 'fantas'],
    'snacks': ['snack', 'galleta', 'galletas', 'papas', 'papitas', 'barrita', 'barritas', 'cereal', 'cereales', 'bocadillo', 'bocadillos', 'dulce', 'dulces', 'golosina', 'golosinas'],
    'salvavida': ['salvavidas'],
    'oreo': ['oreos'],
    'churros': ['churro', 'churrito', 'churritos']
}

CATEGORIAS_PRODUCTOS = {
    'cerveza': ['corona', 'michelob', 'stella', 'heineken', 'budweiser', 'miller', 'tecate', 'modelo'],
    'refresco': ['pepsi', 'coca', 'sprite', 'fanta', 'miranda', 'seven up', '7up'],
    'agua': ['agua', 'h2o', 'aqua'],
    'lacteos': ['leche', 'yogurt', 'queso', 'mantequilla', 'crema'],
    'granos': ['arroz', 'frijol', 'maiz', 'trigo', 'avena'],
    'panaderia': ['pan', 'tortilla', 'galleta', 'pastel'],
    'snacks': ['galleta', 'papas', 'barrita', 'snack', 'cereal', 'bocadillo', 'dulce', 'cheetos', 'doritos', 'ruffles', 'pringles', 'oreo', 'chips', 'salvavida', 'salvavidas'],
    'churros': ['churro', 'churros', 'churrito', 'churritos']
}

PALABRAS_CONSULTAS_COMPLEJAS = {
    'ranking': ['top', 'mejores', 'más vendidos', 'populares', 'ranking'],
    'stock_bajo': ['poco', 'bajo', 'agotándose', 'menos de', 'stock bajo', 'pocas unidades'],
    'comparacion': ['más caro', 'más barato', 'comparar', 'versus', 'diferencia'],
    'ofertas': ['oferta', 'descuento', 'promoción', 'rebaja', 'especial', 'promo'],
    'categoria': ['todos los', 'todas las', 'lista de', 'mostrar todos'],
    'inventario': ['inventario', 'stock total', 'existencias', 'disponibilidad'],
    'disponibles': ['disponibles', 'disponible', 'en stock', 'hay stock'],
    'precio': ['menos de', 'más de', 'entre', 'valen', 'cuestan'],
    'combos': ['combo', 'combos', 'paquete', 'paquetes', 'kit', 'kits', 'promoción'],
    'sin_stock': ['no tienen stock', 'sin stock', 'agotados', 'no disponibles'],
    'superlativo': ['más barata', 'más cara', 'más barato', 'más caro', 'más vendida', 'más vendido', 'menos vendida', 'menos vendido', 'cuál es'],
    'calculo_compra': ['con', 'lempiras', 'cuántas puedo comprar', 'cuántos puedo comprar', 'me puedo llevar', 'si tengo', 'puedo comprar']
}

# Estados de conversación para manejo de memoria
conversaciones_activas = {}

def detectar_calculo_compra(pregunta):
    """
    Detecta si el usuario está preguntando cuánto puede comprar con cierta cantidad de dinero
    """
    pregunta_lower = pregunta.lower()
    
    # Patrones para detectar cálculo de compras
    patrones_compra = [
        r'con\s+(\d+)\s+lempiras?.+cu[aá]ntas?\s+(.+?)\s+puedo\s+comprar',
        r'con\s+(\d+)\s+cu[aá]ntas?\s+(.+?)\s+puedo\s+comprar',
        r'si\s+tengo\s+(\d+).+cu[aá]ntas?\s+(.+?)\s+me\s+puedo\s+llevar',
        r'cu[aá]ntas?\s+(.+?)\s+puedo\s+comprar\s+con\s+(\d+)\s+lempiras?',
        r'con\s+l\.?\s?(\d+).+cu[aá]ntas?\s+(.+?)\s+puedo\s+comprar'
    ]
    
    for patron in patrones_compra:
        match = re.search(patron, pregunta_lower)
        if match:
            grupos = match.groups()
            if len(grupos) == 2:
                try:
                    monto = float(grupos[0])
                    producto = grupos[1].strip()
                    return True, monto, producto
                except ValueError:
                    try:
                        monto = float(grupos[1])
                        producto = grupos[0].strip()
                        return True, monto, producto
                    except ValueError:
                        continue
    
    return False, None, None

def obtener_presentaciones_producto(nombre_producto):
    """
    Obtiene todas las presentaciones disponibles de un producto
    """
    try:
        # Expandir términos de búsqueda
        terminos_expandidos = expandir_terminos_busqueda(nombre_producto)
        
        for termino in terminos_expandidos:
            # Usar stored procedure
            resultados_sp = ejecutar_sp_productos(termino)
            if isinstance(resultados_sp, list) and len(resultados_sp) > 0:
                # Filtrar resultados relevantes
                resultados_filtrados = filtrar_resultados_relevantes(resultados_sp, nombre_producto)
                if resultados_filtrados:
                    return resultados_filtrados
            
            # Búsqueda SQL directa
            sql_consulta = f"""
            SELECT TOP 20 
                vp.ID_PRODUCTO,
                vp.NOMBRE_PRODUCTO,
                vp.Precio1_con_ISV as PRECIO,
                vp.CANT_TOTAL as INVENTARIO,
                'Presentación principal' as PRESENTACION
            FROM V_PRODUCTOS_INFO vp
            WHERE vp.NOMBRE_PRODUCTO LIKE '%{termino}%'
            AND vp.CANT_TOTAL > 0
            ORDER BY vp.Precio1_con_ISV ASC
            """
            
            resultados_sql = ejecutar_sql(sql_consulta)
            if isinstance(resultados_sql, list) and len(resultados_sql) > 0:
                resultados_filtrados = filtrar_resultados_relevantes(resultados_sql, nombre_producto)
                if resultados_filtrados:
                    return resultados_filtrados
        
        return []
        
    except Exception as e:
        logger.error(f"Error obteniendo presentaciones: {e}")
        return []

def agrupar_presentaciones_similares(presentaciones):
    """
    Agrupa presentaciones similares del mismo producto para evitar duplicados confusos
    """
    grupos = {}
    
    for pres in presentaciones:
        nombre_base = pres['NOMBRE_PRODUCTO'].lower()
        
        # Extraer la parte principal del nombre (sin tamaños específicos)
        nombre_simplificado = re.sub(r'\s*\d+\.?\d*\s*(ml|l|lt|g|kg|oz|onzas?)\s*', '', nombre_base)
        nombre_simplificado = re.sub(r'\s*(pequeña?|grande?|mediana?|chica?)\s*', '', nombre_simplificado)
        
        if nombre_simplificado not in grupos:
            grupos[nombre_simplificado] = []
        
        grupos[nombre_simplificado].append(pres)
    
    # Devolver solo los grupos que tengan presentaciones
    resultado = []
    for grupo in grupos.values():
        resultado.extend(grupo)
    
    return resultado

def calcular_compra_optima(monto, presentaciones):
    """
    Calcula la cantidad óptima que se puede comprar con el monto disponible
    """
    if not presentaciones:
        return None
    
    # Ordenar presentaciones por precio (de menor a mayor)
    presentaciones_ordenadas = sorted(presentaciones, key=lambda x: float(x.get('PRECIO', 0)))
    
    mejor_opcion = None
    mayor_cantidad = 0
    
    # Evaluar cada presentación
    for pres in presentaciones_ordenadas:
        try:
            precio = float(pres.get('PRECIO', 0))
            inventario = int(float(pres.get('INVENTARIO', 0)))
            
            if precio <= 0 or inventario <= 0:
                continue
            
            # Calcular cuántas unidades puede comprar
            cantidad_posible = int(monto // precio)
            
            # Limitar por inventario disponible
            cantidad_final = min(cantidad_posible, inventario)
            
            if cantidad_final > 0:
                costo_total = cantidad_final * precio
                sobrante = monto - costo_total
                
                # Esta es una opción válida
                opcion = {
                    'presentacion': pres,
                    'cantidad': cantidad_final,
                    'precio_unitario': precio,
                    'costo_total': costo_total,
                    'sobrante': sobrante,
                    'inventario_disponible': inventario
                }
                
                # Si es la primera opción o da más unidades, es mejor
                if mejor_opcion is None or cantidad_final > mayor_cantidad:
                    mejor_opcion = opcion
                    mayor_cantidad = cantidad_final
        
        except (ValueError, TypeError):
            continue
    
    return mejor_opcion

def generar_respuesta_calculo_compra(monto, producto, presentaciones, user_id=None):
    """
    Genera la respuesta para cálculo de compras
    """
    if not presentaciones:
        # Guardar en memoria que no se encontró el producto
        if user_id:
            conversaciones_activas[user_id] = {
                'ultimo_producto': producto,
                'existe': False,
                'categoria': None
            }
        
        return f"❌ **Lo siento, no encontré {producto} disponible en IA Minimarket del valle.**\n\n" \
               f"💡 Te sugiero verificar el nombre del producto o consultar por productos similares."
    
    # Agrupar presentaciones similares
    presentaciones_agrupadas = agrupar_presentaciones_similares(presentaciones)
    
    # Verificar si hay múltiples tipos/presentaciones
    tipos_diferentes = []
    nombres_vistos = set()
    
    for pres in presentaciones_agrupadas:
        nombre_producto = pres['NOMBRE_PRODUCTO']
        
        # Detectar diferentes tipos (grande, pequeño, lata, botella, etc.)
        nombre_lower = nombre_producto.lower()
        
        # Crear un identificador único por tipo
        tipo_id = nombre_lower
        if tipo_id not in nombres_vistos:
            nombres_vistos.add(tipo_id)
            tipos_diferentes.append(pres)
    
    # Si hay más de un tipo y el usuario no especificó, preguntar
    if len(tipos_diferentes) > 1 and not especifico_presentacion_en_pregunta(producto, tipos_diferentes):
        # Guardar el estado de la conversación
        if user_id:
            conversaciones_activas[user_id] = {
                'tipo': 'calculo_compra',
                'monto': monto,
                'producto': producto,
                'presentaciones': presentaciones_agrupadas,
                'esperando_respuesta': True,
                'ultimo_producto': producto,
                'existe': True
            }
        
        # Generar pregunta sobre presentaciones
        respuesta = f"💰 **Con L.{monto:,.2f} puedes comprar {producto}**, pero tengo varias presentaciones disponibles:\n\n"
        
        for i, pres in enumerate(tipos_diferentes, 1):
            precio = float(pres.get('PRECIO', 0))
            inventario = int(float(pres.get('INVENTARIO', 0)))
            cantidad_posible = int(monto // precio) if precio > 0 else 0
            cantidad_final = min(cantidad_posible, inventario)
            
            respuesta += f"**{i}.** {pres['NOMBRE_PRODUCTO']}\n"
            respuesta += f"   💰 L.{precio:,.2f} cada una\n"
            respuesta += f"   🛒 Podrías comprar: **{cantidad_final} unidades**\n"
            respuesta += f"   📦 Stock disponible: {inventario}\n\n"
        
        respuesta += "🤔 **¿Cuál presentación prefieres?** Puedes responder con el número o el nombre."
        return respuesta
    
    # Si solo hay una presentación o el usuario ya especificó, calcular directamente
    if len(tipos_diferentes) == 1:
        presentacion_elegida = tipos_diferentes[0]
    else:
        # Buscar la presentación más económica
        presentacion_elegida = min(tipos_diferentes, key=lambda x: float(x.get('PRECIO', float('inf'))))
    
    resultado = calcular_compra_optima(monto, [presentacion_elegida])
    
    if not resultado:
        precio_minimo = min(float(p.get('PRECIO', float('inf'))) for p in presentaciones_agrupadas)
        return f"❌ **Con L.{monto:,.2f} no alcanza para ningún {producto}.**\n\n" \
               f"💡 La presentación más económica cuesta L.{precio_minimo:,.2f}.\n" \
               f"🎯 Te recomiendo ahorrar L.{precio_minimo - monto:,.2f} más para poder comprarlo."
    
    # Generar respuesta exitosa
    return generar_respuesta_compra_exitosa(monto, resultado)

def especifico_presentacion_en_pregunta(producto_original, presentaciones):
    """
    Verifica si el usuario especificó una presentación particular en su pregunta original
    """
    producto_lower = producto_original.lower()
    
    # Palabras que indican presentación específica
    palabras_presentacion = ['grande', 'pequeña', 'chica', 'mediana', 'lata', 'botella', 'six-pack', 'pack', 'caja']
    
    # Verificar si mencionó alguna palabra de presentación
    for palabra in palabras_presentacion:
        if palabra in producto_lower:
            return True
    
    # Verificar si mencionó un tamaño específico
    if re.search(r'\d+\.?\d*\s*(ml|l|lt|g|kg|oz)', producto_lower):
        return True
    
    return False

def generar_respuesta_compra_exitosa(monto, resultado):
    """
    Genera una respuesta exitosa para el cálculo de compra
    """
    pres = resultado['presentacion']
    cantidad = resultado['cantidad']
    precio_unitario = resultado['precio_unitario']
    costo_total = resultado['costo_total']
    sobrante = resultado['sobrante']
    inventario = resultado['inventario_disponible']
    
    respuesta = f"✅ **¡Perfecto! Con L.{monto:,.2f} puedes comprar:**\n\n"
    respuesta += f"🛒 **{cantidad} unidades** de {pres['NOMBRE_PRODUCTO']}\n"
    respuesta += f"💰 Precio unitario: L.{precio_unitario:,.2f}\n"
    respuesta += f"💳 Total a pagar: L.{costo_total:,.2f}\n"
    respuesta += f"💵 Te sobra: L.{sobrante:,.2f}\n"
    respuesta += f"📦 Stock disponible: {inventario} unidades\n\n"
    
    # Sugerencias adicionales
    if sobrante >= precio_unitario and (cantidad + 1) <= inventario:
        respuesta += f"💡 **Tip:** Con L.{sobrante:,.2f} adicional podrías comprar 1 unidad más.\n"
    
    if cantidad == inventario:
        respuesta += f"⚠️ **Nota:** Estarías comprando todo el stock disponible.\n"
    
    respuesta += f"\n🎯 ¿Te gustaría ver otras presentaciones o necesitas algo más?"
    
    return respuesta

def procesar_respuesta_presentacion(respuesta_usuario, user_id):
    """
    Procesa la respuesta del usuario cuando elige una presentación
    """
    if user_id not in conversaciones_activas:
        return "❌ No tengo información de tu consulta anterior. Por favor, vuelve a preguntar."
    
    conversacion = conversaciones_activas[user_id]
    
    if conversacion.get('tipo') != 'calculo_compra' or not conversacion.get('esperando_respuesta'):
        return "❌ No estoy esperando una respuesta sobre presentaciones."
    
    monto = conversacion['monto']
    presentaciones = conversacion['presentaciones']
    
    # Intentar identificar la presentación elegida
    respuesta_lower = respuesta_usuario.lower().strip()
    presentacion_elegida = None
    
    # Si responde con número
    if respuesta_lower.isdigit():
        try:
            indice = int(respuesta_lower) - 1
            if 0 <= indice < len(presentaciones):
                presentacion_elegida = presentaciones[indice]
        except ValueError:
            pass
    
    # Si responde con nombre o parte del nombre
    if not presentacion_elegida:
        mejor_match = None
        mejor_score = 0
        
        for pres in presentaciones:
            nombre_pres = pres['NOMBRE_PRODUCTO'].lower()
            score = similitud_texto(respuesta_lower, nombre_pres)
            
            # También verificar si la respuesta está contenida en el nombre
            if respuesta_lower in nombre_pres:
                score += 0.5
            
            if score > mejor_score and score > 0.3:
                mejor_score = score
                mejor_match = pres
        
        presentacion_elegida = mejor_match
    
    # Limpiar conversación
    del conversaciones_activas[user_id]
    
    if not presentacion_elegida:
        return f"❌ No pude identificar la presentación que elegiste. Por favor, vuelve a hacer tu pregunta de compra."
    
    # Calcular compra con la presentación elegida
    resultado = calcular_compra_optima(monto, [presentacion_elegida])
    
    if not resultado:
        precio = float(presentacion_elegida.get('PRECIO', 0))
        return f"❌ **Con L.{monto:,.2f} no alcanza para {presentacion_elegida['NOMBRE_PRODUCTO']}.**\n\n" \
               f"💡 Esta presentación cuesta L.{precio:,.2f}.\n" \
               f"🎯 Necesitas L.{precio - monto:,.2f} más."
    
    return generar_respuesta_compra_exitosa(monto, resultado)

def detectar_intencion_general(pregunta: str) -> str:
    """
    Detecta la intención general del usuario.
    Retorna: "conversacional", "producto", "consulta_sql", "calculo_compra", "respuesta_presentacion", "desconocido"
    """
    pregunta_lower = pregunta.lower().strip()
    
    # Verificar si es cálculo de compra
    es_calculo, monto, producto = detectar_calculo_compra(pregunta)
    if es_calculo:
        return "calculo_compra"
    
    # Patrones conversacionales ampliados
    patrones_conversacionales = [
        r'\b(hola|hi|hey|buenas|buenos días|buenas tardes|buenas noches|saludos|qué tal)\b',
        r'\b(adiós|adios|bye|hasta luego|nos vemos|chao|chau|hasta pronto)\b',
        r'\b(cómo estás|como estas|qué tal|que tal|cómo te va|como te va|cómo andas)\b',
        r'\b(gracias|muchas gracias|te agradezco|thanks|thank you|genial|excelente)\b',
        r'\b(cuenta|cuéntame|cuentame|dime|platícame|platicame|explícame|explicame)\b',
        r'\b(chiste|broma|algo gracioso|hazme reír|divertido)\b',
        r'\b(quién eres|quien eres|qué eres|que eres|tu nombre|cómo te llamas)\b',
        r'\b(qué puedes hacer|que puedes hacer|cómo funcionas|como funcionas|qué haces)\b',
        r'\b(ayuda|ayúdame|ayudame|necesito ayuda|help|socorro)\b',
        r'\b(me gusta|me encanta|está bien|esta bien|ok|okay|vale|de acuerdo)\b',
        r'\b(buen trabajo|bien hecho|excelente trabajo|muy bien|felicidades)\b',
        r'\b(no entiendo|no comprendo|explica|puedes explicar|qué significa)\b',
        r'\b(consejo|tip|sugerencia|recomendación general|qué opinas)\b',
        r'\b(historia|dato curioso|sabías que|sabias que|cuéntame algo)\b',
        r'^(\?+|!+|\.+|ja+|jaja+|je+|jeje+|ji+|jiji+|lol|xd)$',
        r'^(sí|si|no|tal vez|quizás|quizas|puede ser|claro|por supuesto)$'
    ]
    
    for patron in patrones_conversacionales:
        if re.search(patron, pregunta_lower):
            return "conversacional"
    
    if len(pregunta_lower.split()) <= 2 and not any(palabra in pregunta_lower for palabra in 
        ['tienes', 'hay', 'precio', 'cuesta', 'stock', 'cerveza', 'refresco', 'pepsi', 'coca', 'corona']):
        return "conversacional"
    
    es_compleja, tipo_compleja = detectar_consulta_compleja(pregunta)
    if es_compleja:
        return "consulta_sql"
    
    palabras_producto = [
        'producto', 'productos', 'tienes', 'tienen', 'hay', 'existe', 'disponible',
        'precio', 'cuesta', 'vale', 'stock', 'inventario', 'unidades',
        'cerveza', 'refresco', 'agua', 'leche', 'arroz', 'pan', 'snack',
        'corona', 'michelob', 'pepsi', 'coca', 'sprite', 'fanta', 'salvavida', 'oreo'
    ]
    
    # Verificar si menciona productos con "s" al final
    if re.search(r'\b(coronas|pepsis|cocas|sprites|fantas|salvavidas|oreos)\b', pregunta_lower):
        return "producto"
    
    for palabra in palabras_producto:
        if palabra in pregunta_lower:
            if any(marca in pregunta_lower for marca in ['corona', 'michelob', 'pepsi', 'coca', 'sprite', 'fanta', 'salvavida', 'oreo']):
                return "producto"
            elif any(cat in pregunta_lower for cat in ['cerveza', 'refresco', 'agua', 'snack']):
                return "producto"
            else:
                return "consulta_sql"
    
    return "conversacional"

def generar_respuesta_conversacional(pregunta):
    """Genera respuesta conversacional usando Gemini sin consultar SQL"""
    try:
        prompt = f"""
        Eres un asistente virtual amigable de IA Minimarket del valle.
        
        El usuario te ha dicho: "{pregunta}"
        
        INSTRUCCIONES IMPORTANTES:
        1. Sé cálido, amigable y profesional
        2. Si es un saludo, responde de forma natural y ofrece ayuda
        3. Si pregunta qué puedes hacer, menciona que ayudas con:
           - Buscar productos específicos y ver precios
           - Calcular cuánto puede comprar con cierto dinero (ej: "Con 100 lempiras, ¿cuántas cervezas puedo comprar?")
           - Ver inventario y disponibilidad
           - Encontrar las mejores ofertas
           - Consultas complejas sobre el inventario
        4. Si pide un chiste o algo divertido, sé gracioso pero mantén el profesionalismo
        5. Si pregunta quién eres, di que eres el asistente de IA Minimarket del valle
        6. NUNCA inventes información sobre productos, precios o inventario
        7. Si pregunta algo específico sobre productos, sugiere ejemplos como "¿Tienes Corona?" o "Con 100 lempiras, ¿cuántas Pepsi puedo comprar?"
        8. Usa emojis apropiados (😊, 👍, 🛒, ✨, 🎯, 💰, etc.)
        9. Mantén las respuestas concisas y naturales
        10. Si te agradecen o felicitan, responde con humildad y ofrece más ayuda
        
        Responde de forma natural, amigable y conversacional:
        """
        
        model = genai.GenerativeModel("gemini-2.0-flash-exp")
        response = model.generate_content(prompt)
        return response.text.strip()
        
    except Exception as e:
        logger.error(f"Error generando respuesta conversacional: {e}")
        respuestas_fallback = [
            "¡Hola! 😊 Soy el asistente de IA Minimarket del valle. ¿En qué puedo ayudarte hoy?",
            "¡Bienvenido a IA Minimarket del valle! 🛒 Estoy aquí para ayudarte a encontrar lo que necesitas.",
            "¡Hola! ✨ ¿Buscas algún producto en especial? También puedo ayudarte a calcular cuánto puedes comprar con tu presupuesto."
        ]
        import random
        return random.choice(respuestas_fallback)

def similitud_texto(a, b):
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

def normalizar_texto(texto):
    texto = texto.lower().strip()
    texto = re.sub(r'[^\w\s]', '', texto)
    texto = re.sub(r'\s+', ' ', texto)
    return texto

def detectar_consulta_compleja(pregunta):
    """Detecta si la pregunta es una consulta compleja y de qué tipo"""
    pregunta_lower = pregunta.lower()
    
    # Detección mejorada de superlativos
    if any(frase in pregunta_lower for frase in ['cuál es', 'cual es']):
        if any(palabra in pregunta_lower for palabra in ['más barato', 'más barata', 'más caro', 'más cara']):
            return True, 'superlativo'
    
    if any(palabra in pregunta_lower for palabra in PALABRAS_CONSULTAS_COMPLEJAS['superlativo']):
        return True, 'superlativo'
    
    if any(palabra in pregunta_lower for palabra in PALABRAS_CONSULTAS_COMPLEJAS['sin_stock']):
        return True, 'sin_stock'
    
    if 'menos de' in pregunta_lower or 'más de' in pregunta_lower:
        return True, 'precio'
    
    # Detectar consultas de categorías
    if any(frase in pregunta_lower for frase in ['todos los', 'todas las', 'lista de']):
        return True, 'categoria'
    
    for tipo, palabras in PALABRAS_CONSULTAS_COMPLEJAS.items():
        if tipo == 'calculo_compra':  # Skip calculo_compra aquí
            continue
        if any(palabra in pregunta_lower for palabra in palabras):
            return True, tipo
    
    if any(palabra in pregunta_lower for palabra in ['qué', 'cuáles', 'cuántos']) and \
       not any(marca in pregunta_lower for marca in ['corona', 'michelob', 'pepsi', 'coca', 'sprite']):
        return True, 'consulta_general'
    
    return False, None

def analizar_intencion_completa(pregunta):
    """Analiza la intención completa del usuario antes de ejecutar cualquier consulta"""
    pregunta_lower = pregunta.lower()
    
    # Detectar superlativos únicos
    if any(frase in pregunta_lower for frase in ['cuál es', 'cual es']):
        categoria = None
        if 'cerveza' in pregunta_lower:
            categoria = 'cerveza'
        elif 'refresco' in pregunta_lower or 'gaseosa' in pregunta_lower:
            categoria = 'refresco'
        elif 'snack' in pregunta_lower:
            categoria = 'snack'
        
        if 'barato' in pregunta_lower or 'barata' in pregunta_lower:
            return {
                'tipo': 'superlativo_unico',
                'orden': 'ASC',
                'campo': 'precio',
                'limite': 1,
                'requiere_stock': True,
                'categoria': categoria
            }
        elif 'caro' in pregunta_lower or 'cara' in pregunta_lower:
            return {
                'tipo': 'superlativo_unico',
                'orden': 'DESC',
                'campo': 'precio',
                'limite': 1,
                'requiere_stock': True,
                'categoria': categoria
            }
    
    precio_match = re.search(r'menos de (\d+)', pregunta_lower)
    if precio_match:
        return {
            'tipo': 'precio_limite',
            'limite_precio': int(precio_match.group(1)),
            'requiere_stock': True
        }
    
    if any(frase in pregunta_lower for frase in ['no tienen stock', 'sin stock', 'agotados']):
        return {
            'tipo': 'sin_stock',
            'requiere_stock': False,
            'condicion_stock': '= 0'
        }
    
    return None

def expandir_terminos_busqueda(termino_original):
    termino_norm = normalizar_texto(termino_original)
    terminos_expandidos = [termino_norm, termino_original]
    
    # Verificar plurales con "s"
    if termino_norm.endswith('s') and len(termino_norm) > 3:
        singular = termino_norm[:-1]
        terminos_expandidos.append(singular)
        
        # Verificar si el singular está en sinónimos
        for categoria, sinonimos in SINONIMOS_PRODUCTOS.items():
            if singular in sinonimos or singular == categoria:
                terminos_expandidos.extend(sinonimos)
                terminos_expandidos.append(categoria)
    
    for categoria, sinonimos in SINONIMOS_PRODUCTOS.items():
        if termino_norm in sinonimos or termino_norm == categoria:
            terminos_expandidos.extend(sinonimos)
            terminos_expandidos.append(categoria)
    
    for categoria, productos in CATEGORIAS_PRODUCTOS.items():
        if termino_norm == categoria:
            terminos_expandidos.extend(productos)
        elif termino_norm in productos:
            terminos_expandidos.append(categoria)
    
    return list(set(terminos_expandidos))

def extraer_producto_gemini(pregunta):
    """Extrae el nombre del producto usando Gemini"""
    try:
        prompt = f"""
        Extrae el nombre del producto de esta pregunta sobre el inventario de IA Minimarket del valle.
        
        REGLAS:
        1. Si menciona una marca específica (Corona, Michelob, Pepsi, Coca, Sprite, Fanta, Salvavida, Oreo), devuelve SOLO esa marca
        2. Si dice "cerveza Corona" o "cervezas Corona", devuelve "Corona"
        3. Si dice "Coronas" (plural), devuelve "Corona"
        4. Si dice "Pepsis", devuelve "Pepsi"
        5. Si dice solo "cerveza", devuelve "cerveza"
        6. Si dice "refresco" o "gaseosa", devuelve "refresco"
        7. Si dice "snacks" o "galletas", devuelve "snacks"
        8. Si dice "churros", devuelve "churros"
        9. Si no hay producto claro, devuelve "NO_ENCONTRADO"
        
        Pregunta: "{pregunta}"
        
        Responde SOLO con el nombre del producto o "NO_ENCONTRADO":
        """
        
        model = genai.GenerativeModel("gemini-2.0-flash-exp")
        response = model.generate_content(prompt)
        producto = response.text.strip()
        
        if producto == "NO_ENCONTRADO":
            return None
            
        return normalizar_texto(producto)
        
    except Exception as e:
        logger.error(f"Error extrayendo producto con Gemini: {e}")
        return extraer_producto_fallback(pregunta)

def generar_sql_gemini(pregunta):
    """Genera consulta SQL usando Gemini con mejor análisis de intención"""
    try:
        intencion = analizar_intencion_completa(pregunta)
        
        if intencion:
            return procesar_consulta_compleja(pregunta, intencion.get('tipo', 'consulta_general'))
        
        prompt = f"""
        Genera una consulta SQL para IA Minimarket del valle basándote en esta pregunta sobre inventario.
        
        TABLAS DISPONIBLES:
        - V_PRODUCTOS_INFO: ID_PRODUCTO, NOMBRE_PRODUCTO, Precio1_con_ISV, CANT_TOTAL, Categoria
        
        Pregunta: "{pregunta}"
        
        REGLAS ESTRICTAS:
        1. Solo SELECT, no modificaciones
        2. Para productos disponibles: WHERE CANT_TOTAL > 0
        3. Para "más barato": ORDER BY Precio1_con_ISV ASC con TOP 1
        4. Para "más caro": ORDER BY Precio1_con_ISV DESC con TOP 1
        5. Para productos sin stock: WHERE CANT_TOTAL = 0
        6. Siempre incluir las columnas: NOMBRE_PRODUCTO, CANT_TOTAL as INVENTARIO, Precio1_con_ISV as PRECIO
        7. Limitar resultados con TOP 20 para consultas generales
        8. Si pregunta por UNA cosa específica (cuál es, el más), usar TOP 1
        9. Para categorías, usar el campo Categoria
        
        IMPORTANTE: Si el usuario pregunta "¿Cuál es la cerveza más barata?" debe devolver SOLO UNA (TOP 1)
        
        Genera SOLO el código SQL:
        """
        
        model = genai.GenerativeModel("gemini-2.0-flash-exp")
        response = model.generate_content(prompt)
        return limpiar_sql(response.text.strip())
        
    except Exception as e:
        logger.error(f"Error generando SQL con Gemini: {e}")
        return """
            SELECT TOP 20 NOMBRE_PRODUCTO, CANT_TOTAL as INVENTARIO, Precio1_con_ISV as PRECIO
            FROM V_PRODUCTOS_INFO 
            WHERE CANT_TOTAL > 0
            ORDER BY NOMBRE_PRODUCTO
        """

def ejecutar_sql_busqueda(nombre_producto):
    """MODIFICADO: SIEMPRE ejecuta búsqueda SQL para un producto específico"""
    resultados, metodo = buscar_producto_inteligente(nombre_producto)
    return resultados

def formatear_respuesta_producto(resultados, user_id=None, producto_buscado=None):
    """Formatea respuesta para productos de manera amigable con memoria de conversación"""
    if not resultados or len(resultados) == 0:
        # Guardar en memoria que no se encontró el producto
        if user_id and producto_buscado:
            conversaciones_activas[user_id] = {
                'ultimo_producto': producto_buscado,
                'existe': False,
                'categoria': None
            }
        return f"❌ **Lo siento, actualmente no tenemos {producto_buscado} disponible en IA Minimarket del valle.**\n\n" \
               f"📅 Te sugiero consultar nuevamente en unos días o preguntarme por productos similares.\n\n" \
               f"💡 **¿Te gustaría que te muestre otros productos disponibles?**"
    
    # Guardar en memoria que sí se encontró el producto
    if user_id and producto_buscado:
        conversaciones_activas[user_id] = {
            'ultimo_producto': producto_buscado,
            'existe': True,
            'categoria': None,
            'resultados': resultados
        }
    
    return formatear_respuesta_productos(resultados, "", "busqueda_directa")

def formatear_respuesta_sql(resultados):
    """Formatea respuesta para consultas SQL complejas"""
    if not resultados or len(resultados) == 0:
        return "📊 No encontré resultados para tu consulta en IA Minimarket del valle. ¿Podrías reformularla?"
    
    tipo_consulta = "consulta_general"
    if len(resultados) == 1:
        tipo_consulta = "superlativo"
    
    return formatear_respuesta_compleja(resultados, tipo_consulta, "")

def extraer_producto_fallback(pregunta):
    es_compleja, _ = detectar_consulta_compleja(pregunta)
    if es_compleja:
        return None
        
    pregunta_norm = normalizar_texto(pregunta)
    palabras = pregunta_norm.split()
    
    # Incluir plurales
    marcas_conocidas = ['corona', 'coronas', 'michelob', 'pepsi', 'pepsis', 'coca', 'cocas', 
                       'sprite', 'sprites', 'fanta', 'fantas', 'stella', 'heineken', 
                       'salvavida', 'salvavidas', 'oreo', 'oreos']
    
    for palabra in palabras:
        if palabra in marcas_conocidas:
            # Normalizar a singular
            if palabra.endswith('s') and len(palabra) > 3:
                return palabra[:-1]
            return palabra
    
    categorias_conocidas = ['cerveza', 'refresco', 'agua', 'leche', 'arroz', 'pan', 'snacks', 'galletas', 'churros']
    for palabra in palabras:
        if palabra in categorias_conocidas:
            return palabra
    
    palabras_filtradas = [p for p in palabras if len(p) > 2 and p not in ['tienes', 'hay', 'disponible', 'precio', 'cuesta', 'cuanto']]
    
    return palabras_filtradas[0] if palabras_filtradas else None

def buscar_producto_inteligente(termino_busqueda):
    """MODIFICADO: SIEMPRE busca en inventario real"""
    logger.info(f"Buscando producto inteligente: '{termino_busqueda}'")
    
    terminos_expandidos = expandir_terminos_busqueda(termino_busqueda)
    logger.info(f"Términos expandidos: {terminos_expandidos}")
    
    # SIEMPRE intentar con SP de productos primero
    resultados_sp = ejecutar_sp_productos(termino_busqueda)
    if isinstance(resultados_sp, list) and len(resultados_sp) > 0:
        resultados_filtrados = filtrar_resultados_relevantes(resultados_sp, termino_busqueda)
        if resultados_filtrados:
            logger.info(f"Encontrado con SP: {len(resultados_filtrados)} resultados")
            return resultados_filtrados, "stored_procedure"
    
    # Intentar con términos expandidos
    for termino in terminos_expandidos:
        if termino != termino_busqueda:
            resultados_sp = ejecutar_sp_productos(termino)
            if isinstance(resultados_sp, list) and len(resultados_sp) > 0:
                resultados_filtrados = filtrar_resultados_relevantes(resultados_sp, termino_busqueda)
                if resultados_filtrados:
                    logger.info(f"Encontrado con SP expandido ({termino}): {len(resultados_filtrados)} resultados")
                    return resultados_filtrados, "stored_procedure_expandido"
    
    # Si es una categoría, usar SP de categorías
    if termino_busqueda.lower() in ['churros', 'churro', 'churritos']:
        resultados_categoria = ejecutar_sp_categoria('CHURROS')
        if isinstance(resultados_categoria, list) and len(resultados_categoria) > 0:
            logger.info(f"Encontrado con SP categoría CHURROS: {len(resultados_categoria)} resultados")
            return resultados_categoria, "stored_procedure_categoria"
    
    # SQL directo como último recurso - SIEMPRE EJECUTAR
    for termino in terminos_expandidos:
        sql_consulta = f"""
        SELECT TOP 20 
            vp.ID_PRODUCTO,
            vp.NOMBRE_PRODUCTO,
            vp.Precio1_con_ISV as PRECIO,
            vp.CANT_TOTAL as INVENTARIO,
            'Presentación principal' as PRESENTACION
        FROM V_PRODUCTOS_INFO vp
        WHERE vp.NOMBRE_PRODUCTO LIKE '%{termino}%'
        ORDER BY vp.NOMBRE_PRODUCTO
        """
        
        resultados_sql = ejecutar_sql(sql_consulta)
        if isinstance(resultados_sql, list) and len(resultados_sql) > 0:
            resultados_filtrados = filtrar_resultados_relevantes(resultados_sql, termino_busqueda)
            if resultados_filtrados:
                logger.info(f"Encontrado con SQL ({termino}): {len(resultados_filtrados)} resultados")
                return resultados_filtrados, "consulta_sql"
    
    # Si no encuentra nada, devolver lista vacía (NO ASUMIR)
    logger.info(f"No se encontraron resultados para: {termino_busqueda}")
    return [], "no_encontrado"

def ejecutar_sp_categoria(categoria):
    """Ejecuta el stored procedure para buscar productos por categoría"""
    try:
        query = "EXEC [IA].[SPProductos_Categoria] ?"
        resultados = ejecutar_sql(query, (categoria,))
        
        if isinstance(resultados, list) and len(resultados) > 0:
            logger.info(f"SP Categoría ejecutado exitosamente, {len(resultados)} resultados encontrados")
            return resultados
        else:
            logger.warning(f"SP Categoría no devolvió resultados para: {categoria}")
            return []
            
    except Exception as e:
        logger.error(f"Error al ejecutar SP Categoría: {e}")
        return []

def verificar_coincidencia_presentacion(nombre_producto, presentacion_buscada):
    """Verifica si la presentación buscada coincide con el producto"""
    if not presentacion_buscada:
        return True
    
    numeros_buscados = re.findall(r'(\d+\.?\d*)\s*(l|lt|litro|litros|ml|mililitros|g|gramos|kg|kilos|oz|onzas)?', presentacion_buscada.lower())
    
    if not numeros_buscados:
        return True
    
    nombre_lower = nombre_producto.lower()
    for numero, unidad in numeros_buscados:
        if numero in nombre_lower:
            return True
        if unidad:
            patron = f"{numero}\\s*{unidad}"
            if re.search(patron, nombre_lower):
                return True
    
    return False

def filtrar_resultados_relevantes(resultados, termino_original):
    if not resultados:
        return []
    
    termino_norm = normalizar_texto(termino_original)
    
    presentacion_match = re.search(r'(\d+\.?\d*)\s*(l|lt|litro|litros|ml|mililitros|g|gramos|kg|kilos|oz|onzas)', termino_original.lower())
    presentacion_buscada = presentacion_match.group(0) if presentacion_match else None
    
    resultados_con_score = []
    
    for resultado in resultados:
        nombre_producto = normalizar_texto(resultado['NOMBRE_PRODUCTO'])
        
        if presentacion_buscada and not verificar_coincidencia_presentacion(resultado['NOMBRE_PRODUCTO'], presentacion_buscada):
            continue
        
        score = calcular_relevancia(nombre_producto, termino_norm)
        
        if presentacion_buscada and presentacion_buscada in resultado['NOMBRE_PRODUCTO'].lower():
            score += 2.0
        
        if score > 0.3:
            resultado_con_score = resultado.copy()
            resultado_con_score['_relevancia_score'] = score
            resultados_con_score.append(resultado_con_score)
    
    if not resultados_con_score:
        return resultados[:10]
    
    resultados_ordenados = sorted(resultados_con_score, key=lambda x: x['_relevancia_score'], reverse=True)
    
    for resultado in resultados_ordenados:
        if '_relevancia_score' in resultado:
            del resultado['_relevancia_score']
    
    return resultados_ordenados[:10]

def calcular_relevancia(nombre_producto, termino_busqueda):
    score = 0
    
    if termino_busqueda in nombre_producto:
        score += 1.0
    
    if nombre_producto.startswith(termino_busqueda):
        score += 0.8
    
    if nombre_producto.endswith(termino_busqueda):
        score += 0.6
    
    palabras_termino = termino_busqueda.split()
    palabras_producto = nombre_producto.split()
    
    coincidencias_palabras = 0
    for palabra_termino in palabras_termino:
        for palabra_producto in palabras_producto:
            if palabra_termino == palabra_producto:
                coincidencias_palabras += 1
            elif similitud_texto(palabra_termino, palabra_producto) > 0.8:
                coincidencias_palabras += 0.5
    
    if palabras_termino:
        score += (coincidencias_palabras / len(palabras_termino)) * 0.5
    
    score += similitud_texto(nombre_producto, termino_busqueda) * 0.3
    
    return score

def ejecutar_sql(query, params=None):
    try:
        conn_str = (
            f"DRIVER={{ODBC Driver 18 for SQL Server}};"
            f"SERVER={DB_CONFIG['server']};"
            f"DATABASE={DB_CONFIG['database']};"
            f"UID={DB_CONFIG['username']};"
            f"PWD={DB_CONFIG['password']};"
            f"TrustServerCertificate=yes;"
        )
        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()
        
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)
            
        if cursor.description:
            columnas = [column[0] for column in cursor.description]
            resultados = [dict(zip(columnas, row)) for row in cursor.fetchall()]
        else:
            resultados = []
            
        cursor.close()
        conn.close()
        logger.info(f"Consulta ejecutada exitosamente: {query[:100]}...")
        return resultados
    except Exception as e:
        logger.error(f"Error al ejecutar consulta: {e}")
        return {"error": f"Error al ejecutar la consulta SQL: {e}"}

def ejecutar_sp_productos(nombre_producto):
    try:
        query = "EXEC SPProductos_Presentaciones ?"
        resultados = ejecutar_sql(query, (nombre_producto,))
        
        if isinstance(resultados, list) and len(resultados) > 0:
            logger.info(f"SP ejecutado exitosamente, {len(resultados)} resultados encontrados")
            return resultados
        else:
            logger.warning(f"SP no devolvió resultados para: {nombre_producto}")
            return []
            
    except Exception as e:
        logger.error(f"Error al ejecutar SP: {e}")
        return []

def detectar_tipo_consulta(pregunta):
    """Detecta si es búsqueda de producto o consulta SQL compleja"""
    pregunta_lower = pregunta.lower()
    
    es_compleja, tipo_compleja = detectar_consulta_compleja(pregunta)
    if es_compleja:
        return "consulta_compleja", tipo_compleja
    
    palabras_producto = [
        'tienes', 'hay', 'disponible', 'existe', 'tenemos', 'buscar', 'encontrar', 
        'mostrar', 'ver', 'precio', 'cuesta', 'vale', 'costo', 'cuánto', 'stock', 
        'inventario', 'cantidad', 'cuántos', 'corona', 'cerveza', 'michelob', 
        'pepsi', 'coca', 'cola', 'arroz', 'leche', 'pan', 'agua', 'gaseosa',
        'producto', 'productos', 'presentaciones', 'presentacion', 'refresco',
        'snacks', 'galletas', 'papas', 'salvavida', 'oreo'
    ]
    
    if any(palabra in pregunta_lower for palabra in palabras_producto):
        return "busqueda_producto", None
    
    return "consulta_sql", None

def detectar_intencion_usuario(pregunta):
    """Detecta qué tipo de información busca el usuario"""
    pregunta_lower = pregunta.lower()
    
    if any(palabra in pregunta_lower for palabra in ['precio', 'cuesta', 'vale', 'costo', 'cuánto cuesta']):
        return 'precio'
    elif any(palabra in pregunta_lower for palabra in ['stock', 'inventario', 'cantidad', 'cuántas', 'unidades']):
        return 'inventario'
    elif any(palabra in pregunta_lower for palabra in ['presentacion', 'presentaciones', 'tipos', 'variedades']):
        return 'presentaciones'
    elif any(palabra in pregunta_lower for palabra in ['tienes', 'hay', 'disponible', 'existe', 'tenemos']):
        return 'disponibilidad'
    else:
        return 'general'

def procesar_consulta_compleja(pregunta, tipo_consulta):
    """Procesa consultas complejas con análisis de intención mejorado"""
    try:
        pregunta_lower = pregunta.lower()
        
        intencion = analizar_intencion_completa(pregunta)
        
        # Manejo mejorado de superlativos
        if intencion and intencion['tipo'] == 'superlativo_unico':
            categoria = intencion.get('categoria')
            
            if categoria:
                return f"""
                    SELECT TOP 1 
                        NOMBRE_PRODUCTO, 
                        CANT_TOTAL as INVENTARIO, 
                        Precio1_con_ISV as PRECIO
                    FROM V_PRODUCTOS_INFO 
                    WHERE NOMBRE_PRODUCTO LIKE '%{categoria}%' 
                    AND CANT_TOTAL > 0
                    ORDER BY Precio1_con_ISV {intencion['orden']}
                """
            else:
                return f"""
                    SELECT TOP 1 
                        NOMBRE_PRODUCTO, 
                        CANT_TOTAL as INVENTARIO, 
                        Precio1_con_ISV as PRECIO
                    FROM V_PRODUCTOS_INFO 
                    WHERE CANT_TOTAL > 0
                    ORDER BY Precio1_con_ISV {intencion['orden']}
                """
        
        if intencion and intencion['tipo'] == 'precio_limite':
            return f"""
                SELECT TOP 20 
                    NOMBRE_PRODUCTO, 
                    CANT_TOTAL as INVENTARIO, 
                    Precio1_con_ISV as PRECIO
                FROM V_PRODUCTOS_INFO 
                WHERE CANT_TOTAL > 0 
                AND Precio1_con_ISV < {intencion['limite_precio']}
                ORDER BY Precio1_con_ISV ASC
            """
        
        if intencion and intencion['tipo'] == 'sin_stock':
            return """
                SELECT TOP 20 
                    NOMBRE_PRODUCTO, 
                    CANT_TOTAL as INVENTARIO, 
                    Precio1_con_ISV as PRECIO
                FROM V_PRODUCTOS_INFO 
                WHERE CANT_TOTAL = 0
                ORDER BY NOMBRE_PRODUCTO
            """
        
        # Manejo de consultas por categoría
        if tipo_consulta == 'categoria' or any(frase in pregunta_lower for frase in ['todos los', 'todas las']):
            categoria_detectada = None
            
            if 'cerveza' in pregunta_lower:
                categoria_detectada = 'cerveza'
            elif 'refresco' in pregunta_lower or 'gaseosa' in pregunta_lower:
                categoria_detectada = 'refresco'
            elif 'snack' in pregunta_lower or 'galleta' in pregunta_lower:
                categoria_detectada = 'snack'
            elif 'churro' in pregunta_lower:
                categoria_detectada = 'churro'
            
            if categoria_detectada:
                return f"""
                    SELECT TOP 30 
                        NOMBRE_PRODUCTO, 
                        CANT_TOTAL as INVENTARIO, 
                        Precio1_con_ISV as PRECIO
                    FROM V_PRODUCTOS_INFO 
                    WHERE NOMBRE_PRODUCTO LIKE '%{categoria_detectada}%'
                    AND CANT_TOTAL > 0
                    ORDER BY NOMBRE_PRODUCTO
                """
        
        # Casos específicos predefinidos
        if tipo_consulta == 'sin_stock' or 'no tienen stock' in pregunta_lower:
            return """
                SELECT TOP 20 
                    NOMBRE_PRODUCTO, 
                    CANT_TOTAL as INVENTARIO, 
                    Precio1_con_ISV as PRECIO
                FROM V_PRODUCTOS_INFO 
                WHERE CANT_TOTAL = 0
                ORDER BY NOMBRE_PRODUCTO
            """
        
        ejemplos_sql = {
            'stock_bajo': """
                SELECT TOP 20 
                    NOMBRE_PRODUCTO, 
                    CANT_TOTAL as INVENTARIO, 
                    Precio1_con_ISV as PRECIO
                FROM V_PRODUCTOS_INFO 
                WHERE CANT_TOTAL < 10 AND CANT_TOTAL > 0
                ORDER BY CANT_TOTAL ASC
            """,
            'disponibles': """
                SELECT TOP 20 
                    NOMBRE_PRODUCTO, 
                    CANT_TOTAL as INVENTARIO, 
                    Precio1_con_ISV as PRECIO
                FROM V_PRODUCTOS_INFO 
                WHERE CANT_TOTAL > 0
                ORDER BY NOMBRE_PRODUCTO
            """,
            'ofertas': """
                SELECT TOP 20 
                    NOMBRE_PRODUCTO, 
                    CANT_TOTAL as INVENTARIO, 
                    Precio1_con_ISV as PRECIO
                FROM V_PRODUCTOS_INFO 
                WHERE CANT_TOTAL > 0
                ORDER BY PRECIO ASC
            """,
            'combos': """
                SELECT TOP 20 
                    NOMBRE_PRODUCTO, 
                    CANT_TOTAL as INVENTARIO, 
                    Precio1_con_ISV as PRECIO
                FROM V_PRODUCTOS_INFO 
                WHERE (NOMBRE_PRODUCTO LIKE '%combo%' 
                    OR NOMBRE_PRODUCTO LIKE '%paquete%'
                    OR NOMBRE_PRODUCTO LIKE '%pack%')
                AND CANT_TOTAL > 0
                ORDER BY NOMBRE_PRODUCTO
            """
        }
        
        # Manejo específico de snacks
        if 'snack' in pregunta_lower:
            return """
                SELECT TOP 30 
                    NOMBRE_PRODUCTO, 
                    CANT_TOTAL as INVENTARIO, 
                    Precio1_con_ISV as PRECIO
                FROM V_PRODUCTOS_INFO 
                WHERE (
                    NOMBRE_PRODUCTO LIKE '%snack%' OR 
                    NOMBRE_PRODUCTO LIKE '%galleta%' OR 
                    NOMBRE_PRODUCTO LIKE '%papas%' OR 
                    NOMBRE_PRODUCTO LIKE '%barrita%' OR
                    NOMBRE_PRODUCTO LIKE '%cereal%' OR
                    NOMBRE_PRODUCTO LIKE '%dulce%' OR
                    NOMBRE_PRODUCTO LIKE '%chips%' OR
                    NOMBRE_PRODUCTO LIKE '%cheetos%' OR
                    NOMBRE_PRODUCTO LIKE '%doritos%' OR
                    NOMBRE_PRODUCTO LIKE '%salvavida%' OR
                    NOMBRE_PRODUCTO LIKE '%oreo%'
                )
                AND CANT_TOTAL > 0
                ORDER BY NOMBRE_PRODUCTO
            """
        
        if tipo_consulta in ejemplos_sql:
            return ejemplos_sql[tipo_consulta]
        
        # Usar Gemini para consultas más complejas
        prompt = f"""
        Genera una consulta SQL para IA Minimarket del valle para responder esta pregunta sobre inventario y productos.
        
        IMPORTANTE - USA SOLO ESTAS COLUMNAS:
        - Tabla V_PRODUCTOS_INFO: ID_PRODUCTO, NOMBRE_PRODUCTO, Precio1_con_ISV, CANT_TOTAL, Categoria
        - Tabla factura (solo si es necesario): ID_PRODUCTO, FECHA, CANTIDAD
        
        NO USES columnas como FECHA_FACTURA, DESCUENTO, ID_PADRE, ID_HIJO, ES_COMBO
        
        Tipo de consulta: {tipo_consulta}
        Pregunta: "{pregunta}"
        
        REGLAS CRÍTICAS:
        1. Si el usuario pregunta "¿Cuál es la cerveza más barata?" debe devolver SOLO UNA (TOP 1)
        2. SIEMPRE agregar WHERE CANT_TOTAL > 0 si se buscan productos disponibles
        3. Para productos sin stock usar WHERE CANT_TOTAL = 0
        4. Usar LIKE '%término%' para búsquedas de texto
        5. Para combos usar: WHERE NOMBRE_PRODUCTO LIKE '%combo%' OR NOMBRE_PRODUCTO LIKE '%paquete%'
        6. Para "más barato" usar ORDER BY Precio1_con_ISV ASC y TOP 1
        7. Para "más caro" usar ORDER BY Precio1_con_ISV DESC y TOP 1
        8. Para consultas generales usar TOP 20 o TOP 30
        
        Genera SOLO el código SQL:
        """
        
        model = genai.GenerativeModel("gemini-2.0-flash-exp")
        response = model.generate_content(prompt)
        sql = limpiar_sql(response.text.strip())
        
        return sql
        
    except Exception as e:
        logger.error(f"Error generando SQL complejo: {e}")
        return """
            SELECT TOP 20 
                NOMBRE_PRODUCTO, 
                CANT_TOTAL as INVENTARIO, 
                Precio1_con_ISV as PRECIO
            FROM V_PRODUCTOS_INFO 
            WHERE CANT_TOTAL > 0
            ORDER BY NOMBRE_PRODUCTO
        """

def generar_prompt_sql_mejorado(pregunta, contexto_usuario):
    return f"""
Eres un asistente especializado en generar consultas SQL para IA Minimarket del valle.

🔒 **TABLAS Y COLUMNAS DISPONIBLES:**
- V_PRODUCTOS_INFO: ID_PRODUCTO, NOMBRE_PRODUCTO, Precio1_con_ISV, CANT_TOTAL, Categoria
- factura (solo si es necesario para ventas): ID_PRODUCTO, FECHA, CANTIDAD

⚠️ **NO USES ESTAS COLUMNAS (NO EXISTEN):**
- FECHA_FACTURA (usa FECHA)
- DESCUENTO
- ID_PADRE, ID_HIJO
- ES_COMBO

📋 **REGLAS ESTRICTAS:**
1. SOLO consultas SELECT
2. Para "más barato/caro" usar TOP 1, no listados
3. Si buscas productos disponibles, SIEMPRE agregar WHERE CANT_TOTAL > 0
4. Para productos sin stock usar WHERE CANT_TOTAL = 0
5. Para búsquedas de texto usar LIKE '%término%'
6. Para combos: WHERE NOMBRE_PRODUCTO LIKE '%combo%'
7. Para snacks: WHERE NOMBRE_PRODUCTO LIKE '%snack%' OR NOMBRE_PRODUCTO LIKE '%galleta%'
8. Para categorías, usar el campo Categoria cuando sea posible

🎯 **CONTEXTO:** {contexto_usuario}

📝 **PREGUNTA:** "{pregunta}"

IMPORTANTE: Piensa en la intención real del usuario. Si pregunta "¿cuál es la cerveza más barata?" quiere UNA cerveza, no una lista.

Genera SOLO el código SQL:
"""

def limpiar_sql(sql_text):
    sql_text = re.sub(r'```sql\n?', '', sql_text)
    sql_text = re.sub(r'```\n?', '', sql_text)
    
    if sql_text.lower().startswith("sql"):
        sql_text = sql_text[3:].strip()
    
    sql_text = sql_text.replace("`", "")
    sql_text = re.sub(r'--.*$', '', sql_text, flags=re.MULTILINE)
    
    sql_text = sql_text.replace('FECHA_FACTURA', 'FECHA')
    sql_text = re.sub(r'\bDESCUENTO\b', '0 as DESCUENTO', sql_text, flags=re.IGNORECASE)
    sql_text = re.sub(r'\bID_PADRE\b', 'ID_PRODUCTO', sql_text, flags=re.IGNORECASE)
    sql_text = re.sub(r'\bID_HIJO\b', 'ID_PRODUCTO', sql_text, flags=re.IGNORECASE)
    sql_text = re.sub(r'\bES_COMBO\b', "CASE WHEN NOMBRE_PRODUCTO LIKE '%combo%' THEN 1 ELSE 0 END", sql_text, flags=re.IGNORECASE)
    
    if not sql_text.strip().upper().startswith("SELECT"):
        return "SELECT 'Consulta no válida. Solo se permiten consultas SELECT.' AS mensaje;"
    
    operaciones_prohibidas = ['INSERT', 'UPDATE', 'DELETE', 'DROP', 'CREATE', 'ALTER', 'TRUNCATE', 'EXEC']
    sql_upper = sql_text.upper()
    for operacion in operaciones_prohibidas:
        if operacion in sql_upper and operacion != 'EXEC':
            return "SELECT 'Operación no permitida. Solo se permiten consultas SELECT.' AS mensaje;"
    
    return sql_text.strip()

def formatear_respuesta_productos(resultados, pregunta, metodo_busqueda):
    """Función mejorada para generar respuestas más naturales y humanas"""
    
    if not resultados or len(resultados) == 0:
        return generar_respuesta_sin_stock(pregunta)
    
    intencion = detectar_intencion_usuario(pregunta)
    
    es_superlativo = any(palabra in pregunta.lower() for palabra in ['más barato', 'más barata', 'más caro', 'más cara'])
    
    productos_agrupados = {}
    for item in resultados:
        id_producto = item['ID_PRODUCTO']
        if id_producto not in productos_agrupados:
            productos_agrupados[id_producto] = {
                'nombre': item['NOMBRE_PRODUCTO'],
                'inventario': item.get('INVENTARIO', 0),
                'presentaciones': []
            }
        
        productos_agrupados[id_producto]['presentaciones'].append({
            'presentacion': item.get('PRESENTACION', 'Presentación principal'),
            'precio': item.get('PRECIO', 0)
        })
    
    respuesta = ""
    
    if es_superlativo and len(productos_agrupados) == 1:
        producto = list(productos_agrupados.values())[0]
        nombre = producto['nombre']
        inventario = producto['inventario']
        presentaciones = producto['presentaciones']
        
        try:
            inventario_num = float(inventario) if inventario is not None else 0
        except:
            inventario_num = 0
        
        if inventario_num > 0 and presentaciones:
            precio = presentaciones[0]['precio']
            try:
                precio_num = float(precio) if precio is not None else 0
                precio_formateado = f"L {precio_num:,.2f}" if precio_num > 0 else "Por consultar"
            except:
                precio_formateado = "Por consultar"
            
            if 'barato' in pregunta.lower() or 'barata' in pregunta.lower():
                respuesta = f"✅ **La cerveza más económica disponible en IA Minimarket del valle es:**\n\n"
            else:
                respuesta = f"✅ **La cerveza de mayor precio disponible en IA Minimarket del valle es:**\n\n"
            
            respuesta += f"🍺 **{nombre}**\n"
            respuesta += f"💰 Precio: {precio_formateado}\n"
            respuesta += f"📦 Stock: {inventario_num:,.0f} unidades disponibles\n\n"
            respuesta += "¿Te gustaría ver más opciones o comparar con otros productos?"
            
            return respuesta
    
    for idx, (id_producto, info) in enumerate(productos_agrupados.items()):
        nombre = info['nombre']
        inventario = info['inventario']
        presentaciones = info['presentaciones']
        
        try:
            inventario_num = float(inventario) if inventario is not None else 0
        except (ValueError, TypeError):
            inventario_num = 0
        
        if intencion == 'disponibilidad':
            respuesta += generar_respuesta_disponibilidad(nombre, inventario_num, presentaciones)
        elif intencion == 'precio':
            respuesta += generar_respuesta_precio(nombre, inventario_num, presentaciones)
        elif intencion == 'inventario':
            respuesta += generar_respuesta_inventario(nombre, inventario_num, presentaciones)
        elif intencion == 'presentaciones':
            respuesta += generar_respuesta_presentaciones(nombre, inventario_num, presentaciones)
        else:
            respuesta += generar_respuesta_general(nombre, inventario_num, presentaciones)
        
        if idx < len(productos_agrupados) - 1:
            respuesta += "\n" + "─" * 40 + "\n\n"
    
    respuesta += generar_frase_seguimiento(len(productos_agrupados), intencion)
    
    return respuesta

def generar_respuesta_sin_stock(pregunta):
    """Genera respuesta cuando no hay productos disponibles"""
    producto = extraer_producto_gemini(pregunta)
    
    if not producto:
        return "🔍 No pude identificar un producto específico en tu consulta. ¿Podrías decirme el nombre o la categoría?"
    
    respuestas = [
        f"❌ **Lo siento, actualmente no tenemos {producto} disponible en IA Minimarket del valle.**\n\n"
        f"📅 Te sugiero consultar nuevamente en unos días o preguntarme por productos similares.\n\n"
        f"💡 **¿Te gustaría que te muestre otros productos disponibles?**",
        
        f"❌ **No encontré {producto} en nuestro inventario actual de IA Minimarket del valle.**\n\n"
        f"🔄 Nuestro stock se actualiza constantemente, te recomiendo verificar más tarde.\n\n"
        f"🤝 **¿Puedo ayudarte a buscar algo similar?**",
        
        f"❌ **No hay existencias de {producto} en este momento en IA Minimarket del valle.**\n\n"
        f"📲 Si lo deseas, puedes dejar tu contacto para avisarte cuando esté disponible.\n\n"
        f"🛒 **¿Necesitas ver otros productos que sí tenemos?**"
    ]
    
    import random
    return random.choice(respuestas)

def generar_respuesta_disponibilidad(nombre, inventario, presentaciones):
    """Respuesta enfocada en disponibilidad"""
    if inventario > 0:
        respuesta = f"✅ **{nombre}**\n"
        respuesta += f"📦 {inventario:,.0f} unidades disponibles\n"
        
        if presentaciones:
            respuesta += f"💰 Presentaciones: {len(presentaciones)}\n"
            for i, pres in enumerate(presentaciones[:5], 1):
                precio = pres['precio']
                try:
                    precio_num = float(precio) if precio is not None else 0
                    precio_formateado = f"L {precio_num:,.2f}" if precio_num > 0 else "Por consultar"
                except:
                    precio_formateado = "Por consultar"
                respuesta += f"{i}. {pres['presentacion']} - {precio_formateado}\n"
    else:
        respuesta = f"❌ **{nombre}**\n"
        respuesta += f"📦 Sin stock - Temporalmente agotado\n"
    
    return respuesta + "\n"

def generar_respuesta_precio(nombre, inventario, presentaciones):
    """Respuesta enfocada en precios"""
    estado = "✅" if inventario > 0 else "❌"
    respuesta = f"{estado} **{nombre}**\n"
    
    if inventario > 0:
        respuesta += f"📦 {inventario:,.0f} unidades disponibles\n"
    else:
        respuesta += f"📦 Sin stock - Temporalmente agotado\n"
    
    if presentaciones:
        respuesta += f"💰 Presentaciones: {len(presentaciones)}\n"
        for i, pres in enumerate(presentaciones[:5], 1):
            precio = pres['precio']
            try:
                precio_num = float(precio) if precio is not None else 0
                precio_formateado = f"L {precio_num:,.2f}" if precio_num > 0 else "Por consultar"
            except:
                precio_formateado = "Por consultar"
            respuesta += f"{i}. {pres['presentacion']} - {precio_formateado}\n"
    
    return respuesta + "\n"

def generar_respuesta_inventario(nombre, inventario, presentaciones):
    """Respuesta enfocada en inventario/stock"""
    estado = "✅" if inventario > 0 else "❌"
    respuesta = f"{estado} **{nombre}**\n"
    
    if inventario > 0:
        respuesta += f"📦 {inventario:,.0f} unidades disponibles\n"
        
        if inventario < 10:
            respuesta += f"⚠️ ¡Últimas unidades! Realiza tu pedido pronto\n"
        elif inventario < 50:
            respuesta += f"📉 Stock limitado\n"
    else:
        respuesta += f"📦 Sin stock - Temporalmente agotado\n"
    
    if presentaciones:
        respuesta += f"💰 Presentaciones: {len(presentaciones)}\n"
        for i, pres in enumerate(presentaciones[:5], 1):
            precio = pres['precio']
            try:
                precio_num = float(precio) if precio is not None else 0
                precio_formateado = f"L {precio_num:,.2f}" if precio_num > 0 else "Por consultar"
            except:
                precio_formateado = "Por consultar"
            respuesta += f"{i}. {pres['presentacion']} - {precio_formateado}\n"
    
    return respuesta + "\n"

def generar_respuesta_presentaciones(nombre, inventario, presentaciones):
    """Respuesta enfocada en presentaciones"""
    estado = "✅" if inventario > 0 else "❌"
    respuesta = f"{estado} **{nombre}**\n"
    
    if inventario > 0:
        respuesta += f"📦 {inventario:,.0f} unidades disponibles\n"
    else:
        respuesta += f"📦 Sin stock - Temporalmente agotado\n"
    
    if presentaciones:
        respuesta += f"💰 Presentaciones: {len(presentaciones)}\n"
        for i, pres in enumerate(presentaciones, 1):
            precio = pres['precio']
            try:
                precio_num = float(precio) if precio is not None else 0
                precio_formateado = f"L {precio_num:,.2f}" if precio_num > 0 else "Por consultar"
            except:
                precio_formateado = "Por consultar"
            respuesta += f"{i}. {pres['presentacion']} - {precio_formateado}\n"
    
    return respuesta + "\n"

def generar_respuesta_general(nombre, inventario, presentaciones):
    """Respuesta general completa"""
    estado = "✅" if inventario > 0 else "❌"
    respuesta = f"{estado} **{nombre}**\n"
    
    if inventario > 0:
        respuesta += f"📦 {inventario:,.0f} unidades disponibles\n"
    else:
        respuesta += f"📦 Sin stock - Temporalmente agotado\n"
    
    if presentaciones:
        respuesta += f"💰 Presentaciones: {len(presentaciones)}\n"
        for i, pres in enumerate(presentaciones[:5], 1):
            precio = pres['precio']
            try:
                precio_num = float(precio) if precio is not None else 0
                precio_formateado = f"L {precio_num:,.2f}" if precio_num > 0 else "Por consultar"
            except:
                precio_formateado = "Por consultar"
            respuesta += f"{i}. {pres['presentacion']} - {precio_formateado}\n"
    
    return respuesta + "\n"

def generar_frase_seguimiento(num_productos, intencion):
    """Genera frases de seguimiento personalizadas"""
    import random
    
    frases_generales = [
        "\n¿Deseas ver otra marca o producto relacionado?",
        "\n¿Te ayudo con algo más?",
        "\n¿Necesitas información adicional?",
        "\n¿Te gustaría ver más productos?"
    ]
    
    frases_precio = [
        "\n¿Te interesa conocer los precios de otros productos?",
        "\n¿Quieres comparar precios con productos similares?"
    ]
    
    frases_inventario = [
        "\n¿Necesitas verificar el stock de otros productos?",
        "\n¿Buscas algo más? Puedo revisar nuestro inventario."
    ]
    
    frases_sin_resultados = [
        "\n¿Te gustaría que te muestre productos similares?",
        "\n¿Quieres que busque alternativas disponibles?"
    ]
    
    if num_productos == 0:
        return random.choice(frases_sin_resultados)
    elif intencion == 'precio':
        return random.choice(frases_precio)
    elif intencion == 'inventario':
        return random.choice(frases_inventario)
    else:
        return random.choice(frases_generales)

def formatear_respuesta_compleja(resultados, tipo_consulta, pregunta):
    """Formatea respuestas para consultas complejas de manera humanizada con diseño mejorado"""
    
    if not resultados or len(resultados) == 0:
        if tipo_consulta == 'sin_stock':
            return "📊 **¡Excelente noticia! Todos los productos tienen stock disponible en IA Minimarket del valle en este momento.** ✅\n\n¿Te gustaría ver los productos con menos inventario?"
        else:
            return "📊 No encontré resultados para tu consulta. Intenta con otros criterios."
    
    respuesta = ""
    
    # Títulos según tipo de consulta
    if tipo_consulta == 'stock_bajo':
        respuesta = "📊 **Estos son los productos con menos de 10 unidades en stock:**\n\n"
    elif tipo_consulta == 'ranking':
        respuesta = "📊 **Top productos más vendidos:**\n\n"
    elif tipo_consulta == 'ofertas':
        respuesta = "📊 **Productos en oferta:**\n\n"
    elif tipo_consulta == 'disponibles':
        respuesta = "📊 **Productos disponibles:**\n\n"
    elif tipo_consulta == 'precio':
        respuesta = "📊 **Productos en tu rango de precio:**\n\n"
    elif tipo_consulta == 'combos':
        respuesta = "📊 **Combos y paquetes disponibles:**\n\n"
    elif tipo_consulta == 'comparacion':
        respuesta = "📊 **Comparación de productos:**\n\n"
    elif tipo_consulta == 'sin_stock':
        respuesta = "📊 **Productos sin stock actualmente:**\n\n"
    elif tipo_consulta == 'superlativo':
        if 'barato' in pregunta.lower() or 'barata' in pregunta.lower():
            respuesta = "📊 **Producto más económico encontrado:**\n\n"
        else:
            respuesta = "📊 **Producto de mayor precio encontrado:**\n\n"
    else:
        respuesta = "📊 **Resultados de tu consulta:**\n\n"
    
    # Para superlativos con un solo resultado
    if tipo_consulta == 'superlativo' and len(resultados) == 1:
        item = resultados[0]
        nombre = item.get('NOMBRE_PRODUCTO', 'Producto')
        inventario = item.get('INVENTARIO', item.get('CANT_TOTAL', 0))
        precio = item.get('PRECIO', item.get('Precio1_con_ISV', 0))
        
        try:
            inventario_num = float(inventario) if inventario is not None else 0
            precio_num = float(precio) if precio is not None else 0
        except:
            inventario_num = 0
            precio_num = 0
        
        if 'barato' in pregunta.lower() or 'barata' in pregunta.lower():
            respuesta = f"✅ **El producto más económico disponible en IA Minimarket del valle es:**\n\n"
        else:
            respuesta = f"✅ **El producto de mayor precio disponible en IA Minimarket del valle es:**\n\n"
        
        respuesta += f"✅ **{nombre}**\n"
        respuesta += f"📦 {inventario_num:,.0f} unidades disponibles\n"
        respuesta += f"💰 Presentaciones: 1\n"
        respuesta += f"1. Presentación principal - L {precio_num:,.2f}\n\n"
        respuesta += "¿Te gustaría ver más opciones o comparar con productos similares?"
        
        return respuesta
    
    # Formatear múltiples resultados
    for idx, item in enumerate(resultados[:20], 1):
        nombre = item.get('NOMBRE_PRODUCTO', 'Producto')
        inventario = item.get('INVENTARIO', item.get('CANT_TOTAL', 0))
        precio = item.get('PRECIO', item.get('Precio1_con_ISV', 0))
        
        try:
            inventario_num = float(inventario) if inventario is not None else 0
            precio_num = float(precio) if precio is not None else 0
        except:
            inventario_num = 0
            precio_num = 0
        
        # Determinar estado
        if inventario_num > 0:
            estado = "✅"
            estado_texto = "Disponible"
        else:
            estado = "❌"
            estado_texto = "Sin stock"
        
        respuesta += f"{estado} **{nombre}**\n"
        respuesta += f"📦 {inventario_num:,.0f} unidades disponibles\n"
        
        # Formatear como presentaciones
        if precio_num > 0:
            respuesta += f"💰 Presentaciones: 1\n"
            respuesta += f"1. Presentación principal - L {precio_num:,.2f}\n"
        
        # Información adicional según el tipo
        if tipo_consulta == 'stock_bajo' and inventario_num < 5:
            respuesta += f"⚠️ ¡Crítico! Reabastecer urgente\n"
        elif tipo_consulta == 'ranking' and 'TOTAL_VENTAS' in item:
            ventas = item.get('TOTAL_VENTAS', 0)
            respuesta += f"🏆 {ventas} ventas este mes\n"
        
        # Separador entre productos (excepto el último)
        if idx < len(resultados) and idx < 20:
            respuesta += "\n" + "─" * 40 + "\n\n"
    
    # Agregar recomendaciones según el tipo
    if tipo_consulta == 'stock_bajo':
        respuesta += "\n\n💡 ¡Te recomendamos reabastecer pronto estos productos! ¿Deseas ver los más vendidos o filtrar por categoría?"
    elif tipo_consulta == 'ranking':
        respuesta += "\n\n🏆 ¿Te gustaría ver el stock actual de estos productos o conocer sus precios?"
    elif tipo_consulta == 'sin_stock':
        respuesta += "\n\n📦 Estos productos necesitan reabastecimiento. ¿Quieres ver productos similares disponibles?"
    elif tipo_consulta == 'superlativo':
        respuesta += "\n\n🎯 ¿Te gustaría ver más opciones o comparar con productos similares?"
    else:
        respuesta += f"\n\n🔍 Total de resultados encontrados: {len(resultados)}"
        respuesta += "\n¿Necesitas información más específica sobre algún producto?"
    
    return respuesta

def formatear_resultados_sql(resultados):
    if not resultados:
        return "No se encontraron resultados para esta consulta."
    
    if len(resultados) == 1 and 'mensaje' in resultados[0]:
        return resultados[0]['mensaje']
    
    respuesta = f"✅ **Resultados encontrados:** {len(resultados)}\n\n"
    
    for i, fila in enumerate(resultados, 1):
        respuesta += f"📋 **Resultado {i}:**\n"
        
        for columna, valor in fila.items():
            valor_formateado = formatear_valor(valor, columna)
            respuesta += f"• **{columna}:** {valor_formateado}\n"
        
        respuesta += "\n"
    
    return respuesta

def formatear_valor(valor, columna):
    if valor is None:
        return "N/A"
    elif isinstance(valor, datetime):
        return valor.strftime("%Y-%m-%d %H:%M:%S")
    elif isinstance(valor, float):
        if any(keyword in columna.lower() for keyword in ['precio', 'total', 'costo', 'valor', 'ganancia', 'venta']):
            return f"L {valor:,.2f}"
        else:
            return f"{valor:.2f}"
    elif isinstance(valor, int) and 'id' not in columna.lower():
        return f"{valor:,}"
    else:
        return str(valor)

def obtener_contexto_usuario(pregunta):
    contexto = ""
    
    if any(palabra in pregunta.lower() for palabra in ['hoy', 'ayer', 'semana', 'mes', 'día']):
        contexto += "CONTEXTO_FECHA: Fecha actual del sistema: GETDATE()\n"
    
    if any(palabra in pregunta.lower() for palabra in ['stock', 'inventario', 'cantidad', 'existencia']):
        contexto += "CONTEXTO_INVENTARIO: Usa CANT_TOTAL para cantidades en stock\n"
    
    if any(palabra in pregunta.lower() for palabra in ['venta', 'factura', 'cliente', 'vendedor']):
        contexto += "CONTEXTO_VENTAS: Usa la tabla factura para información de ventas\n"
    
    if any(palabra in pregunta.lower() for palabra in ['disponible', 'disponibles', 'hay', 'existe']):
        contexto += "CONTEXTO_DISPONIBILIDAD: Agregar WHERE CANT_TOTAL > 0\n"
    
    return contexto

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json()
    print("🟢 Datos recibidos:", data)
    pregunta_usuario = data.get("message", "")
    user_id = data.get("user_id", "default_user")
    
    if not pregunta_usuario:
        return jsonify({"response": "❌ No se recibió una pregunta válida."})
    
    try:
        # Verificar si hay memoria de conversación previa
        memoria_usuario = conversaciones_activas.get(user_id, {})
        
        # Si el usuario pregunta por detalles de un producto que no existe
        if memoria_usuario.get('ultimo_producto') and not memoria_usuario.get('existe', True):
            pregunta_lower = pregunta_usuario.lower()
            if any(palabra in pregunta_lower for palabra in ['precio', 'cuesta', 'vale', 'presentacion', 'detalles', 'dame']):
                producto_anterior = memoria_usuario['ultimo_producto']
                respuesta = f"❌ **Sigo sin encontrar {producto_anterior} en nuestro inventario de IA Minimarket del valle.**\n\n" \
                           f"💡 ¿Te gustaría consultar por otro producto o ver alguna recomendación?"
                
                return jsonify({
                    "response": respuesta,
                    "tipo_respuesta": "memoria_producto_inexistente",
                    "producto_recordado": producto_anterior,
                    "requirio_sql": False
                })
        
        # Verificar si el usuario está esperando respuesta de presentación
        if user_id in conversaciones_activas and conversaciones_activas[user_id].get('esperando_respuesta'):
            respuesta = procesar_respuesta_presentacion(pregunta_usuario, user_id)
            return jsonify({
                "response": respuesta,
                "tipo_respuesta": "calculo_compra_resultado",
                "requirio_sql": True
            })
        
        # Detectar intención general
        intencion = detectar_intencion_general(pregunta_usuario)
        
        logger.info(f"Pregunta: '{pregunta_usuario}' - Intención detectada: {intencion}")
        
        if intencion == "conversacional":
            respuesta = generar_respuesta_conversacional(pregunta_usuario)
            
            return jsonify({
                "response": respuesta,
                "tipo_respuesta": "conversacional",
                "requirio_sql": False
            })
        
        elif intencion == "calculo_compra":
            es_calculo, monto, producto = detectar_calculo_compra(pregunta_usuario)
            
            if es_calculo:
                presentaciones = obtener_presentaciones_producto(producto)
                respuesta = generar_respuesta_calculo_compra(monto, producto, presentaciones, user_id)
                
                return jsonify({
                    "response": respuesta,
                    "tipo_respuesta": "calculo_compra",
                    "monto": monto,
                    "producto": producto,
                    "total_presentaciones": len(presentaciones),
                    "requirio_sql": True
                })
            else:
                return jsonify({
                    "response": "🔍 No pude identificar el monto o el producto en tu consulta de compra. ¿Podrías reformularla? Ejemplo: 'Con 100 lempiras, ¿cuántas Corona puedo comprar?'",
                    "tipo_respuesta": "error_calculo_compra",
                    "requirio_sql": False
                })
        
        elif intencion == "producto":
            nombre_producto = extraer_producto_gemini(pregunta_usuario)
            
            if not nombre_producto:
                return jsonify({
                    "response": "🔍 No pude identificar el producto que buscas en IA Minimarket del valle. ¿Podrías ser más específico? Por ejemplo: '¿Tienes Corona?' o '¿Hay Pepsi?'",
                    "tipo_respuesta": "error_producto",
                    "requirio_sql": False
                })
            
            # SIEMPRE ejecutar búsqueda SQL
            datos = ejecutar_sql_busqueda(nombre_producto)
            respuesta = formatear_respuesta_producto(datos, user_id, nombre_producto)
            
            return jsonify({
                "response": respuesta,
                "tipo_respuesta": "busqueda_producto",
                "producto_buscado": nombre_producto,
                "total_resultados": len(datos),
                "requirio_sql": True
            })
        
        elif intencion == "consulta_sql":
            consulta = generar_sql_gemini(pregunta_usuario)
            datos = ejecutar_sql(consulta)
            
            if isinstance(datos, dict) and "error" in datos:
                return jsonify({
                    "response": f"❌ Error en la consulta: {datos['error']}",
                    "tipo_respuesta": "error_sql",
                    "requirio_sql": True
                })
            
            respuesta = formatear_respuesta_sql(datos)
            
            return jsonify({
                "response": respuesta,
                "tipo_respuesta": "consulta_compleja",
                "total_resultados": len(datos) if isinstance(datos, list) else 0,
                "requirio_sql": True
            })
        
        else:
            respuesta = generar_respuesta_conversacional(pregunta_usuario)
            
            return jsonify({
                "response": respuesta,
                "tipo_respuesta": "conversacional",
                "requirio_sql": False
            })
        
    except Exception as e:
        logger.error(f"Error inesperado: {e}")
        return jsonify({
            "response": f"❌ Ocurrió un error inesperado en IA Minimarket del valle. Por favor, intenta de nuevo o reformula tu pregunta. 😅",
            "error_tipo": type(e).__name__,
            "tipo_respuesta": "error_sistema"
        })

@app.route("/health")
def health_check():
    try:
        test_query = "SELECT 1 AS test"
        resultado = ejecutar_sql(test_query)
        
        if isinstance(resultado, dict) and "error" in resultado:
            return jsonify({
                "status": "unhealthy", 
                "database": "disconnected",
                "error": resultado["error"]
            })
        
        return jsonify({
            "status": "healthy", 
            "database": "connected",
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({
            "status": "unhealthy", 
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        })

@app.route("/ejemplos")
def ejemplos():
    ejemplos = {
        "saludos_conversacion": [
            "Hola, ¿cómo estás?",
            "Buenos días",
            "¿Qué tal?",
            "Gracias",
            "¿Qué me recomiendas?",
            "Cuéntame un chiste",
            "¿Quién eres?",
            "¿Cómo funcionas?",
            "Me gusta la idea",
            "Buen trabajo",
            "¿Qué puedes hacer?"
        ],
        "busqueda_productos": [
            "¿Tienes Corona?",
            "¿Hay Michelob?",
            "¿Tienes Coronas?",
            "¿Hay Pepsis?",
            "¿Existe Pepsi?",
            "¿Tienen cerveza?",
            "¿Hay refrescos?",
            "¿Qué snacks tienen?",
            "¿Cuánto cuesta la cerveza?",
            "Precio de la Coca-Cola",
            "¿Tienen churros?"
        ],
        "calculo_compras": [
            "Con 100 lempiras, ¿cuántas Corona puedo comprar?",
            "Si tengo 300, ¿cuántas Michelob me puedo llevar?",
            "¿Cuántas Salvavida puedo comprar con 100 lempiras?",
            "Cuántas Oreos puedo comprar con 150 lempiras?",
            "Con 50 lempiras, ¿qué cerveza puedo comprar?",
            "¿Cuántos refrescos puedo comprar con 200 lempiras?"
        ],
        "consultas_complejas": [
            "¿Cuál es la cerveza más barata?",
            "¿Qué productos tienen menos de 10 unidades?",
            "Top 10 productos más vendidos",
            "¿Qué productos no tienen stock?",
            "Productos que valen menos de 20 lempiras",
            "¿Qué combos tienen disponibles?",
            "Mostrar productos con stock bajo",
            "¿Cuál es el refresco más caro?",
            "Todos los snacks disponibles"
        ],
        "ejemplos_mixtos": [
            "Hola, necesito saber si tienen Corona",
            "Gracias por la información, ¿qué más tienen?",
            "¿Me puedes recomendar una cerveza barata?",
            "Buenos días, ¿cuál es el refresco más vendido?",
            "Con 100 lempiras, ¿cuántas cervezas puedo comprar?"
        ]
    }
    return jsonify(ejemplos)

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=5000)
