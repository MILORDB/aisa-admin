import os
import io
from datetime import datetime
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm, inch
from reportlab.lib.enums import TA_RIGHT, TA_LEFT, TA_CENTER
from reportlab.pdfgen import canvas
import json

class GeneradorReportes:
    """Clase para generar reportes en PDF"""
    
    def __init__(self, negocio_id, negocio_nombre, negocio_telefono, negocio_direccion=None):
        self.negocio_id = negocio_id
        self.negocio_nombre = negocio_nombre
        self.negocio_telefono = negocio_telefono
        self.negocio_direccion = negocio_direccion
        self.buffer = io.BytesIO()
    
    def _crear_encabezado_factura(self, elementos, styles, titulo, numero_factura, fecha, cliente, empresa=None):
        """Crea el encabezado para facturas"""
        
        estilo_nombre_negocio = ParagraphStyle(
            'NombreNegocio',
            parent=styles['Heading1'],
            fontSize=18,
            textColor=colors.HexColor('#6c3ce0'),
            alignment=TA_CENTER,
            spaceAfter=2
        )
        
        estilo_datos_negocio = ParagraphStyle(
            'DatosNegocio',
            parent=styles['Normal'],
            fontSize=10,
            textColor=colors.HexColor('#666666'),
            alignment=TA_CENTER,
            spaceAfter=2
        )
        
        estilo_titulo_factura = ParagraphStyle(
            'TituloFactura',
            parent=styles['Heading2'],
            fontSize=16,
            textColor=colors.HexColor('#333333'),
            alignment=TA_CENTER,
            spaceAfter=12
        )
        
        estilo_datos_cliente = ParagraphStyle(
            'DatosCliente',
            parent=styles['Normal'],
            fontSize=10,
            textColor=colors.HexColor('#333333'),
            spaceAfter=4
        )
        
        estilo_separador = ParagraphStyle(
            'Separador',
            parent=styles['Normal'],
            fontSize=8,
            textColor=colors.HexColor('#cccccc'),
            alignment=TA_CENTER
        )
        
        # Nombre del negocio
        elementos.append(Paragraph(self.negocio_nombre, estilo_nombre_negocio))
        
        # Teléfono del negocio
        if self.negocio_telefono:
            elementos.append(Paragraph(f"📞 {self.negocio_telefono}", estilo_datos_negocio))
        
        # Dirección del negocio
        if self.negocio_direccion:
            elementos.append(Paragraph(f"📍 {self.negocio_direccion}", estilo_datos_negocio))
        
        # Línea separadora
        elementos.append(Paragraph("─" * 60, estilo_separador))
        elementos.append(Spacer(1, 0.3*cm))
        
        # Título de factura y número
        elementos.append(Paragraph(f"{titulo}", estilo_titulo_factura))
        
        estilo_info = ParagraphStyle(
            'InfoFactura',
            parent=styles['Normal'],
            fontSize=10,
            textColor=colors.HexColor('#333333'),
            alignment=TA_CENTER,
            spaceAfter=8
        )
        elementos.append(Paragraph(f"N° {numero_factura} | {fecha}", estilo_info))
        
        # Línea separadora
        elementos.append(Paragraph("─" * 60, estilo_separador))
        elementos.append(Spacer(1, 0.3*cm))
        
        # Datos del cliente
        if cliente:
            elementos.append(Paragraph(f"<b>Cliente:</b> {cliente}", estilo_datos_cliente))
        if empresa:
            elementos.append(Paragraph(f"<b>Empresa:</b> {empresa}", estilo_datos_cliente))
        
        elementos.append(Spacer(1, 0.3*cm))
        
        return elementos

    def _crear_pie_pagina_factura(self, elementos, styles):
        """Crea el pie de página para facturas"""
        estilo_pie = ParagraphStyle(
            'PieFactura',
            parent=styles['Normal'],
            fontSize=8,
            textColor=colors.HexColor('#999999'),
            alignment=TA_CENTER,
            spaceBefore=20
        )
        
        elementos.append(Spacer(1, 1*cm))
        elementos.append(Paragraph(
            f"Documento generado por AIsa - Sistema de Gestión Empresarial | {datetime.now().strftime('%Y')}",
            estilo_pie
        ))
        elementos.append(Paragraph(
            "Este documento es un comprobante de venta",
            estilo_pie
        ))
        
        return elementos

    # ============================================
    # GENERAR FACTURA DE VENTA
    # ============================================
    
    def generar_factura_venta(self, venta, items, es_oferta=False):
        """
        Genera una factura de venta en PDF
        
        Args:
            venta: Datos de la venta (dict)
            items: Lista de items de la venta (productos y servicios)
            es_oferta: Si es una oferta (True) o venta real (False)
        """
        doc = SimpleDocTemplate(
            self.buffer,
            pagesize=A4,
            rightMargin=2*cm,
            leftMargin=2*cm,
            topMargin=1.5*cm,
            bottomMargin=1.5*cm
        )
        
        styles = getSampleStyleSheet()
        elementos = []
        
        titulo = "📄 OFERTA DE VENTA" if es_oferta else "🧾 FACTURA DE VENTA"
        numero = venta.get('factura', f"FAC-{venta.get('id', 0)}")
        fecha = venta.get('fecha', datetime.now().strftime("%Y-%m-%d %H:%M"))
        cliente = venta.get('cliente', 'Cliente')
        empresa = venta.get('empresa', '')
        
        elementos = self._crear_encabezado_factura(
            elementos, styles, titulo, numero, fecha, cliente, empresa
        )
        
        if items:
            tabla_datos = []
            headers = ["Cant.", "Descripción", "Precio Unit.", "Subtotal"]
            tabla_datos.append(headers)
            
            for item in items:
                cantidad = item.get('cantidad', 1)
                descripcion = item.get('nombre', '-')
                precio = item.get('precio', 0)
                subtotal = item.get('subtotal', precio * cantidad)
                
                fila = [
                    str(cantidad),
                    descripcion,
                    f"${precio:,.2f}",
                    f"${subtotal:,.2f}"
                ]
                tabla_datos.append(fila)
            
            tabla = Table(tabla_datos, colWidths=[2*cm, 8*cm, 3.5*cm, 3.5*cm])
            tabla.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#6c3ce0')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
                ('TOPPADDING', (0, 0), (-1, 0), 8),
                
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 9),
                ('ALIGN', (0, 1), (0, -1), 'CENTER'),
                ('ALIGN', (2, 1), (3, -1), 'RIGHT'),
                ('TOPPADDING', (0, 1), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
                
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cccccc')),
                ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#999999')),
                
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor('#f9f9f9'), colors.white]),
            ]))
            
            elementos.append(tabla)
            
            elementos.append(Spacer(1, 0.5*cm))
            
            total = sum(item.get('subtotal', item.get('precio', 0) * item.get('cantidad', 1)) for item in items)
            
            estilo_total = ParagraphStyle(
                'TotalFactura',
                parent=styles['Heading3'],
                fontSize=14,
                textColor=colors.HexColor('#6c3ce0'),
                alignment=TA_RIGHT,
                spaceBefore=8
            )
            
            estilo_observacion = ParagraphStyle(
                'Observacion',
                parent=styles['Normal'],
                fontSize=9,
                textColor=colors.HexColor('#666666'),
                alignment=TA_LEFT,
                spaceBefore=12
            )
            
            elementos.append(Paragraph(f"<b>TOTAL: ${total:,.2f}</b>", estilo_total))
            
            if es_oferta:
                elementos.append(Paragraph(
                    "📌 Esta es una OFERTA DE VENTA. No afecta el inventario.",
                    estilo_observacion
                ))
                elementos.append(Paragraph(
                    "El cliente puede aceptar la oferta y convertirla en venta real.",
                    estilo_observacion
                ))
            
            estado = venta.get('estado', 'pagado')
            estado_text = {
                'pagado': '✅ Pagado',
                'pendiente': '⏳ Pendiente',
                'cancelado': '❌ Cancelado',
                'transferencia': '💳 Transferencia',
                'oferta': '📄 Oferta'
            }.get(estado, estado)
            
            estilo_estado = ParagraphStyle(
                'EstadoFactura',
                parent=styles['Normal'],
                fontSize=10,
                textColor=colors.HexColor('#333333'),
                alignment=TA_RIGHT,
                spaceBefore=4
            )
            elementos.append(Paragraph(f"Estado: {estado_text}", estilo_estado))
            
        else:
            estilo_vacio = ParagraphStyle(
                'Vacio',
                parent=styles['Normal'],
                fontSize=12,
                textColor=colors.HexColor('#888888'),
                alignment=TA_CENTER,
                spaceBefore=20
            )
            elementos.append(Paragraph("No hay items en esta venta", estilo_vacio))
        
        elementos.append(Spacer(1, 1*cm))
        
        estilo_firma = ParagraphStyle(
            'Firma',
            parent=styles['Normal'],
            fontSize=10,
            textColor=colors.HexColor('#666666'),
            alignment=TA_RIGHT,
            spaceBefore=8
        )
        
        elementos.append(Paragraph("_________________________________", estilo_firma))
        elementos.append(Paragraph(f"{self.negocio_nombre}", estilo_firma))
        elementos.append(Paragraph("Representante Legal", estilo_firma))
        
        elementos = self._crear_pie_pagina_factura(elementos, styles)
        doc.build(elementos)
        
        pdf_bytes = self.buffer.getvalue()
        self.buffer.close()
        return pdf_bytes

    # ============================================
    # REPORTE DE CONTRATOS
    # ============================================
    
    def generar_reporte_contratos(self, contratos, tipo_reporte='todos'):
        """Genera un reporte PDF de contratos"""
        doc = SimpleDocTemplate(
            self.buffer,
            pagesize=A4,
            rightMargin=2*cm,
            leftMargin=2*cm,
            topMargin=2*cm,
            bottomMargin=2*cm
        )
        
        styles = getSampleStyleSheet()
        elementos = []
        
        if tipo_reporte == 'activos':
            titulo = "📊 REPORTE DE CONTRATOS ACTIVOS"
        elif tipo_reporte == 'vencidos':
            titulo = "📊 REPORTE DE CONTRATOS VENCIDOS"
        else:
            titulo = "📊 REPORTE GENERAL DE CONTRATOS"
        
        total = len(contratos)
        activos = len([c for c in contratos if c.get('estado') == 'activo'])
        vencidos = len([c for c in contratos if c.get('estado') == 'vencido'])
        subtitulo = f"Total: {total} contratos | Activos: {activos} | Vencidos: {vencidos}"
        
        elementos = self._crear_encabezado(elementos, styles, titulo, subtitulo)
        
        if contratos:
            tabla_datos = []
            headers = ["N° Contrato", "Empresa / TCP / MIPYME", "Fecha Inicio", "Fecha Fin", "Gastos ($)", "Estado"]
            tabla_datos.append(headers)
            
            for c in contratos:
                gastos = c.get('monto', 0)
                estado = c.get('estado', 'desconocido')
                if estado == 'activo':
                    estado_display = '🟢 Activo'
                elif estado == 'vencido':
                    estado_display = '🔴 Vencido'
                else:
                    estado_display = '⚪ ' + estado.capitalize()
                
                fila = [
                    c.get('numero_contrato', '-'),
                    c.get('empresa', '-'),
                    c.get('fecha_inicio', '-'),
                    c.get('fecha_fin', '-'),
                    f"${gastos:,.2f}",
                    estado_display
                ]
                tabla_datos.append(fila)
            
            tabla = Table(tabla_datos, colWidths=[2.2*cm, 5*cm, 2.5*cm, 2.5*cm, 2.5*cm, 2.8*cm])
            tabla.setStyle(self._estilo_tabla())
            elementos.append(tabla)
            
            elementos.append(Spacer(1, 0.5*cm))
            total_gastos = sum(c.get('monto', 0) for c in contratos)
            
            estilo_resumen = ParagraphStyle(
                'Resumen',
                parent=styles['Normal'],
                fontSize=10,
                textColor=colors.HexColor('#333333'),
                alignment=TA_RIGHT,
                spaceBefore=8,
                spaceAfter=4
            )
            
            estilo_total = ParagraphStyle(
                'Total',
                parent=styles['Heading3'],
                fontSize=12,
                textColor=colors.HexColor('#6c3ce0'),
                alignment=TA_RIGHT,
                spaceBefore=4,
                spaceAfter=8
            )
            
            elementos.append(Paragraph(f"Total de contratos: {len(contratos)}", estilo_resumen))
            elementos.append(Paragraph(f"Total de gastos acumulados: ${total_gastos:,.2f}", estilo_total))
            
            elementos.append(Spacer(1, 1*cm))
            estilo_firma = ParagraphStyle(
                'Firma',
                parent=styles['Normal'],
                fontSize=10,
                textColor=colors.HexColor('#666666'),
                alignment=TA_RIGHT,
                spaceBefore=8
            )
            
            elementos.append(Paragraph("_________________________________", estilo_firma))
            elementos.append(Paragraph(f"{self.negocio_nombre}", estilo_firma))
            elementos.append(Paragraph("Representante Legal", estilo_firma))
        else:
            estilo_vacio = ParagraphStyle(
                'Vacio',
                parent=styles['Normal'],
                fontSize=12,
                textColor=colors.HexColor('#888888'),
                alignment=TA_CENTER,
                spaceBefore=20
            )
            elementos.append(Paragraph("No hay contratos para mostrar", estilo_vacio))
        
        elementos = self._crear_pie_pagina(elementos, styles)
        doc.build(elementos)
        
        pdf_bytes = self.buffer.getvalue()
        self.buffer.close()
        return pdf_bytes

    # ============================================
    # REPORTE DE INGRESOS
    # ============================================
    
    def generar_reporte_ingresos(self, ventas, total_ingresos, total_ventas, periodo=None):
        """Genera un reporte PDF de ingresos"""
        doc = SimpleDocTemplate(
            self.buffer,
            pagesize=landscape(A4),
            rightMargin=2*cm,
            leftMargin=2*cm,
            topMargin=2*cm,
            bottomMargin=2*cm
        )
        
        styles = getSampleStyleSheet()
        elementos = []
        
        titulo = "💰 REPORTE DE INGRESOS"
        subtitulo = f"Total de ingresos: ${total_ingresos:,.2f} | Total de ventas: {total_ventas}"
        if periodo:
            subtitulo += f" | Período: {periodo}"
        
        elementos = self._crear_encabezado(elementos, styles, titulo, subtitulo)
        
        if ventas:
            tabla_datos = []
            headers = ["# Venta", "Cliente", "Producto/Servicio", "Empresa", "Cantidad", "Total ($)", "Fecha", "Estado"]
            tabla_datos.append(headers)
            
            for v in ventas[:50]:
                estado = v.get('estado', 'pagado')
                if estado == 'pagado':
                    estado_display = '✅ Pagado'
                elif estado == 'pendiente':
                    estado_display = '⏳ Pendiente'
                elif estado == 'transferencia':
                    estado_display = '💳 Transferencia'
                elif estado == 'oferta':
                    estado_display = '📄 Oferta'
                else:
                    estado_display = '❌ Cancelado'
                
                fila = [
                    f"#{v.get('id', '')}",
                    v.get('cliente', '-'),
                    v.get('producto', '-'),
                    v.get('empresa', '-') or '-',
                    str(v.get('cantidad', 1)),
                    f"${v.get('total', 0):,.2f}",
                    v.get('fecha', '-'),
                    estado_display
                ]
                tabla_datos.append(fila)
            
            tabla = Table(tabla_datos, colWidths=[1.5*cm, 3.5*cm, 4*cm, 3*cm, 1.5*cm, 2.5*cm, 2.5*cm, 2.5*cm])
            tabla.setStyle(self._estilo_tabla())
            elementos.append(tabla)
            
            elementos.append(Spacer(1, 0.5*cm))
            
            estilo_resumen = ParagraphStyle(
                'Resumen',
                parent=styles['Normal'],
                fontSize=10,
                textColor=colors.HexColor('#333333'),
                alignment=TA_RIGHT,
                spaceBefore=8,
                spaceAfter=4
            )
            
            estilo_total = ParagraphStyle(
                'Total',
                parent=styles['Heading3'],
                fontSize=12,
                textColor=colors.HexColor('#6c3ce0'),
                alignment=TA_RIGHT,
                spaceBefore=4,
                spaceAfter=8
            )
            
            elementos.append(Paragraph(f"Total de ventas: {len(ventas)}", estilo_resumen))
            elementos.append(Paragraph(f"Ingresos totales: ${total_ingresos:,.2f}", estilo_total))
        else:
            estilo_vacio = ParagraphStyle(
                'Vacio',
                parent=styles['Normal'],
                fontSize=12,
                textColor=colors.HexColor('#888888'),
                alignment=TA_CENTER,
                spaceBefore=20
            )
            elementos.append(Paragraph("No hay ventas registradas para este período", estilo_vacio))
        
        elementos = self._crear_pie_pagina(elementos, styles)
        doc.build(elementos)
        
        pdf_bytes = self.buffer.getvalue()
        self.buffer.close()
        return pdf_bytes

    # ============================================
    # REPORTE DE PRODUCTOS
    # ============================================
    
    def generar_reporte_productos(self, productos):
        """Genera un reporte PDF de productos en almacén"""
        doc = SimpleDocTemplate(
            self.buffer,
            pagesize=landscape(A4),
            rightMargin=2*cm,
            leftMargin=2*cm,
            topMargin=2*cm,
            bottomMargin=2*cm
        )
        
        styles = getSampleStyleSheet()
        elementos = []
        
        titulo = "📦 REPORTE DE INVENTARIO - PRODUCTOS EN ALMACÉN"
        
        total_productos = len(productos)
        total_stock = sum(p.get('stock', 0) for p in productos)
        stock_bajo = len([p for p in productos if p.get('stock', 0) <= (p.get('stock_minimo', 3))])
        stock_agotado = len([p for p in productos if p.get('stock', 0) == 0])
        valor_total = sum(p.get('precio', 0) * p.get('stock', 0) for p in productos)
        
        subtitulo = (
            f"Total: {total_productos} productos | "
            f"Stock total: {total_stock} unidades | "
            f"Stock bajo: {stock_bajo} | "
            f"Agotados: {stock_agotado} | "
            f"Valor total: ${valor_total:,.2f}"
        )
        
        elementos = self._crear_encabezado(elementos, styles, titulo, subtitulo)
        
        if productos:
            tabla_datos = []
            headers = ["ID", "Producto", "Categoría", "Precio ($)", "Stock", "Stock Mínimo", "Estado", "Valor ($)"]
            tabla_datos.append(headers)
            
            productos_ordenados = sorted(productos, key=lambda x: x.get('stock', 0))
            
            for p in productos_ordenados:
                stock = p.get('stock', 0)
                stock_minimo = p.get('stock_minimo', 3)
                
                if stock == 0:
                    estado = '🚫 Agotado'
                elif stock <= stock_minimo:
                    estado = '⚠️ Bajo stock'
                else:
                    estado = '✅ Normal'
                
                valor = stock * p.get('precio', 0)
                
                fila = [
                    str(p.get('id', '')),
                    p.get('nombre', '-'),
                    p.get('categoria', '-') or '-',
                    f"${p.get('precio', 0):,.2f}",
                    str(stock),
                    str(stock_minimo),
                    estado,
                    f"${valor:,.2f}"
                ]
                tabla_datos.append(fila)
            
            tabla = Table(tabla_datos, colWidths=[1.5*cm, 4*cm, 3.5*cm, 2.5*cm, 2*cm, 2.5*cm, 3*cm, 2.5*cm])
            tabla.setStyle(self._estilo_tabla())
            elementos.append(tabla)
            
            elementos.append(Spacer(1, 0.5*cm))
            
            estilo_resumen = ParagraphStyle(
                'Resumen',
                parent=styles['Normal'],
                fontSize=10,
                textColor=colors.HexColor('#333333'),
                alignment=TA_RIGHT,
                spaceBefore=8,
                spaceAfter=4
            )
            
            estilo_total = ParagraphStyle(
                'Total',
                parent=styles['Heading3'],
                fontSize=12,
                textColor=colors.HexColor('#6c3ce0'),
                alignment=TA_RIGHT,
                spaceBefore=4,
                spaceAfter=8
            )
            
            elementos.append(Paragraph(f"Total de productos: {total_productos}", estilo_resumen))
            elementos.append(Paragraph(f"Stock total: {total_stock} unidades", estilo_resumen))
            elementos.append(Paragraph(f"Valor total del inventario: ${valor_total:,.2f}", estilo_total))
        else:
            estilo_vacio = ParagraphStyle(
                'Vacio',
                parent=styles['Normal'],
                fontSize=12,
                textColor=colors.HexColor('#888888'),
                alignment=TA_CENTER,
                spaceBefore=20
            )
            elementos.append(Paragraph("No hay productos registrados en el almacén", estilo_vacio))
        
        elementos = self._crear_pie_pagina(elementos, styles)
        doc.build(elementos)
        
        pdf_bytes = self.buffer.getvalue()
        self.buffer.close()
        return pdf_bytes

    # ============================================
    # MÉTODOS AUXILIARES
    # ============================================
    
    def _crear_encabezado(self, elementos, styles, titulo_reporte, subtitulo=None):
        """Crea el encabezado común para todos los reportes"""
        estilo_titulo = ParagraphStyle(
            'TituloNegocio',
            parent=styles['Heading1'],
            fontSize=16,
            textColor=colors.HexColor('#6c3ce0'),
            alignment=TA_RIGHT,
            spaceAfter=2
        )
        
        estilo_telefono = ParagraphStyle(
            'TelefonoNegocio',
            parent=styles['Normal'],
            fontSize=11,
            textColor=colors.HexColor('#444444'),
            alignment=TA_RIGHT,
            spaceAfter=8
        )
        
        estilo_fecha = ParagraphStyle(
            'FechaReporte',
            parent=styles['Normal'],
            fontSize=10,
            textColor=colors.HexColor('#666666'),
            alignment=TA_RIGHT,
            spaceAfter=20
        )
        
        estilo_titulo_reporte = ParagraphStyle(
            'TituloReporte',
            parent=styles['Heading2'],
            fontSize=14,
            textColor=colors.HexColor('#333333'),
            alignment=TA_CENTER,
            spaceAfter=12
        )
        
        estilo_subtitulo = ParagraphStyle(
            'Subtitulo',
            parent=styles['Normal'],
            fontSize=10,
            textColor=colors.HexColor('#666666'),
            alignment=TA_CENTER,
            spaceAfter=16
        )
        
        elementos.append(Paragraph(self.negocio_nombre, estilo_titulo))
        
        telefono_text = f"📞 {self.negocio_telefono}" if self.negocio_telefono else "📞 Sin teléfono registrado"
        elementos.append(Paragraph(telefono_text, estilo_telefono))
        
        fecha_actual = datetime.now().strftime("%d de %B de %Y, %H:%M")
        elementos.append(Paragraph(f"📅 Reporte generado: {fecha_actual}", estilo_fecha))
        
        elementos.append(Spacer(1, 0.5*cm))
        
        elementos.append(Paragraph(titulo_reporte, estilo_titulo_reporte))
        
        if subtitulo:
            elementos.append(Paragraph(subtitulo, estilo_subtitulo))
        
        elementos.append(Spacer(1, 0.5*cm))
        
        return elementos

    def _crear_pie_pagina(self, elementos, styles):
        """Crea el pie de página común"""
        estilo_pie = ParagraphStyle(
            'Pie',
            parent=styles['Normal'],
            fontSize=8,
            textColor=colors.HexColor('#999999'),
            alignment=TA_CENTER,
            spaceBefore=20
        )
        
        elementos.append(Spacer(1, 1*cm))
        elementos.append(Paragraph(
            f"Reporte generado por AIsa - Sistema de Gestión Empresarial | {datetime.now().strftime('%Y')}",
            estilo_pie
        ))
        
        return elementos

    def _estilo_tabla(self):
        """Retorna el estilo común para las tablas"""
        return TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#6c3ce0')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ('TOPPADDING', (0, 0), (-1, 0), 8),
            
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('TOPPADDING', (0, 1), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
            
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cccccc')),
            ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#999999')),
            
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor('#f9f9f9'), colors.white]),
        ])
