"""Datos de ejemplo para trabajar el front sin depender de API Gateway.

El formato de SERVICIOS replica el documento de DynamoDB (tabla `servicios`).
FACTURAS, CLIENTES y PAGOS son datos de ejemplo del modelo MySQL.
"""

IVA = {"nombre": "IVA", "tasa": 0.16, "tipo": "traslado"}


def svc(n, clave, nombre, descripcion, categoria, precio, unidad, caracteristicas,
        activo=True, **extra):
    d = {
        "id_servicio": f"SRV-{n:03d}",
        "clave": clave,
        "nombre": nombre,
        "descripcion": descripcion,
        "categoria": categoria,
        "precio_unitario": precio,
        "unidad_medida": unidad,
        "activo": activo,
        "impuesto": dict(IVA),
        "caracteristicas": [
            {"nombre": a, "tipo": b, "valor": c} for a, b, c in caracteristicas
        ],
    }
    d.update(extra)
    return d


SERVICIOS = [
    svc(1, "HOST-BAS", "Hosting Basico",
        "Hosting compartido para sitios web pequenos y medianos",
        "Hosting y dominios", 349, "Mes", [
            ("Almacenamiento", "tecnica", "20 GB SSD"),
            ("Transferencia mensual", "tecnica", "100 GB"),
            ("Dominios incluidos", "tecnica", "1"),
            ("Cuentas de correo", "tecnica", "10"),
            ("Certificado SSL", "tecnica", "Incluido"),
            ("Respaldo", "tecnica", "Diario automatico"),
            ("Disponibilidad garantizada", "comercial", "99.9 por ciento"),
            ("Soporte", "comercial", "24/7 por correo"),
            ("Migracion gratuita", "comercial", "Incluida"),
        ]),
    svc(2, "SEC-PEN", "Prueba de Penetracion Web",
        "Auditoria de seguridad sobre aplicaciones web expuestas a internet",
        "Ciberseguridad", 38500, "Servicio", [
            ("Metodologia", "tecnica", "OWASP Top 10"),
            ("Alcance", "tecnica", "Hasta 3 aplicaciones"),
            ("Tipo de prueba", "tecnica", "Caja gris"),
            ("Reporte ejecutivo", "comercial", "Incluido"),
            ("Retest posterior", "comercial", "1 incluido a los 30 dias"),
            ("Modalidad", "comercial", "Remota"),
        ],
        requiere_contrato_confidencialidad=True, duracion_estimada_dias=15),
    svc(3, "WEB-LAND", "Desarrollo de Landing Page",
        "Pagina web de una sola seccion orientada a conversion",
        "Desarrollo web", 4500, "Servicio", [
            ("Secciones", "tecnica", "1"),
            ("Diseno responsivo", "tecnica", "Si"),
        ]),
    svc(4, "SOP-MEN", "Soporte Tecnico Mensual",
        "Soporte remoto para equipos de oficina",
        "Soporte", 950, "Mes", [
            ("Horas incluidas", "comercial", "10"),
        ]),
    svc(5, "HOST-PRO", "Hosting Profesional",
        "Hosting con mayor capacidad para tiendas y sitios con trafico constante",
        "Hosting y dominios", 899, "Mes", [
            ("Almacenamiento", "tecnica", "80 GB SSD"),
            ("Transferencia mensual", "tecnica", "500 GB"),
            ("Dominios incluidos", "tecnica", "5"),
            ("Respaldo", "tecnica", "Diario automatico"),
            ("Soporte", "comercial", "24/7 por chat"),
        ]),
    svc(6, "DOM-MX", "Registro de dominio .mx",
        "Registro y renovacion de dominio .mx",
        "Hosting y dominios", 599, "Ano", [
            ("Vigencia", "comercial", "12 meses"),
            ("Panel DNS", "tecnica", "Incluido"),
        ]),
    svc(7, "SSL-ANU", "Certificado SSL",
        "Certificado de validacion de dominio para cifrar el trafico del sitio",
        "Ciberseguridad", 1200, "Ano", [
            ("Validacion", "tecnica", "Dominio"),
            ("Instalacion", "comercial", "Incluida"),
        ]),
    svc(8, "SEC-VUL", "Analisis de Vulnerabilidades",
        "Escaneo automatizado y revision de hallazgos de infraestructura",
        "Ciberseguridad", 18500, "Servicio", [
            ("Alcance", "tecnica", "Hasta 50 IPs"),
            ("Reporte ejecutivo", "comercial", "Incluido"),
        ], duracion_estimada_dias=7),
    svc(9, "WEB-COR", "Sitio Web Corporativo",
        "Sitio institucional de hasta 8 secciones con panel de contenido",
        "Desarrollo web", 28000, "Servicio", [
            ("Secciones", "tecnica", "Hasta 8"),
            ("Diseno responsivo", "tecnica", "Si"),
            ("Panel de contenido", "tecnica", "Incluido"),
            ("Capacitacion", "comercial", "2 horas"),
        ]),
    svc(10, "WEB-MAN", "Mantenimiento Web",
        "Actualizaciones, correcciones y monitoreo de un sitio existente",
        "Desarrollo web", 1800, "Mes", [
            ("Horas incluidas", "comercial", "5"),
            ("Monitoreo", "tecnica", "Disponibilidad cada 5 minutos"),
        ]),
    svc(11, "NUB-RES", "Respaldo en la Nube",
        "Copias de seguridad cifradas con retencion de 30 dias",
        "Nube y respaldos", 450, "Mes", [
            ("Almacenamiento", "tecnica", "200 GB"),
            ("Retencion", "tecnica", "30 dias"),
            ("Cifrado", "tecnica", "AES-256"),
        ]),
    svc(12, "NUB-MIG", "Migracion a la Nube",
        "Traslado de servidores y bases de datos a infraestructura en la nube",
        "Nube y respaldos", 15000, "Servicio", [
            ("Ventana de migracion", "comercial", "Fin de semana"),
            ("Pruebas posteriores", "comercial", "Incluidas"),
        ], activo=False),
]

CLIENTES = [
    {"id": "CLI-001", "razon_social": "Consultoria Sur SA de CV", "rfc": "CSU210315AB1",
     "cp": "62000", "email": "contacto@consultoriasur.example", "activo": True},
    {"id": "CLI-002", "razon_social": "Taller Mecanico Ortega", "rfc": "OORM800512KT4",
     "cp": "62050", "email": "ortega@taller.example", "activo": True},
    {"id": "CLI-003", "razon_social": "Panaderia La Espiga SA de CV", "rfc": "PES190823HJ9",
     "cp": "62270", "email": "pagos@laespiga.example", "activo": False},
]

FACTURAS = [
    {"folio": "FAC-0001", "cliente": "Consultoria Sur SA de CV", "fecha": "12 oct 2026",
     "subtotal": 349.00, "iva": 55.84, "total": 404.84, "estatus": "pagada"},
    {"folio": "FAC-0002", "cliente": "Taller Mecanico Ortega", "fecha": "13 oct 2026",
     "subtotal": 4500.00, "iva": 720.00, "total": 5220.00, "estatus": "vigente"},
    {"folio": "FAC-0003", "cliente": "Consultoria Sur SA de CV", "fecha": "13 oct 2026",
     "subtotal": 38500.00, "iva": 6160.00, "total": 44660.00, "estatus": "vigente"},
    {"folio": "FAC-0004", "cliente": "Panaderia La Espiga SA de CV", "fecha": "02 oct 2026",
     "subtotal": 950.00, "iva": 152.00, "total": 1102.00, "estatus": "cancelada"},
]

PAGOS = [
    {"id": 1, "folio": "FAC-0001", "fecha": "12 oct 2026", "forma": "03 Transferencia electronica",
     "monto": 404.84, "referencia": "SPEI-88213"},
    {"id": 2, "folio": "FAC-0003", "fecha": "14 oct 2026", "forma": "01 Efectivo",
     "monto": 10000.00, "referencia": "Anticipo"},
]
