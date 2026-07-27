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
from reportlab.lib.fonts import addMapping
import json

class GeneradorReportes:
    """Clase para generar reportes de contratos en PDF"""
    
    def __init__(self, negocio_id, negocio_nombre, negocio_telefono):
        self.negocio_id = negocio_id
        self.negocio_nombre = negocio_nombre
        self.negocio_telefono = negocio_telefono
        self.buffer = io.BytesIO()
        
    def generar_reporte_contratos(self, contratos, tipo_reporte='todos'):
        """
        Genera un reporte PDF de contratos
        
        Args:
            contratos: Lista de contratos con sus datos
            tipo_reporte: 'todos', 'activos', 'vencidos'
        """
        # Crear el documento
        doc = SimpleDocTemplate(
            self.buffer,
            pagesize=A4,
            rightMargin=2*cm,
            leftMargin=2*cm,
            topMargin=2*cm,
            bottomMargin=2*cm
        )
        
        # Estilos
        styles = getSampleStyleSheet()
        
        # Estilo para el título del negocio (derecha)
        estilo_titulo = ParagraphStyle(
            'TituloNegocio',
            parent=styles['Heading1'],
            fontSize=16,
            textColor=colors.HexColor('#6c3ce0'),
            alignment=TA_RIGHT,
            spaceAfter=2
        )
        
        # Estilo para teléfono (derecha)
        estilo_telefono = ParagraphStyle(
            'TelefonoNegocio',
            parent=styles['Normal'],
            fontSize=11,
            textColor=colors.HexColor('#444444'),
            alignment=TA_RIGHT,
            spaceAfter=8
        )
        
        # Estilo para fecha (derecha)
        estilo_fecha = ParagraphStyle(
            'FechaReporte',
            parent=styles['Normal'],
            fontSize=10,
            textColor=colors.HexColor('#666666'),
            alignment=TA_RIGHT,
            spaceAfter=20
        )
        
        # Estilo para el título del reporte (centro)
        estilo_titulo_reporte = ParagraphStyle(
            'TituloReporte',
            parent=styles['Heading2'],
            fontSize=14,
            textColor=colors.HexColor('#333333'),
            alignment=TA_CENTER,
            spaceAfter=12
        )
        
        # Estilo para subtítulo (centro)
        estilo_subtitulo = ParagraphStyle(
            'Subtitulo',
            parent=styles['Normal'],
            fontSize=10,
            textColor=colors.HexColor('#666666'),
            alignment=TA_CENTER,
            spaceAfter=16
        )
        
        # Estilo para celdas de tabla
        estilo_celda = ParagraphStyle(
            'Celda',
            parent=styles['Normal'],
            fontSize=9,
            textColor=colors.HexColor('#333333'),
            alignment=TA_LEFT
        )
        
        # Estilo para celdas de monto (derecha)
        estilo_monto = ParagraphStyle(
            'Monto',
            parent=styles['Normal'],
            fontSize=9,
            textColor=colors.HexColor('#333333'),
            alignment=TA_RIGHT
        )
        
        # Elementos del documento
        elementos = []
        
        # ============================================
        # 1. ENCABEZADO (Derecha)
        # ============================================
        
        # Nombre del negocio
        elementos.append(Paragraph(self.negocio_nombre, estilo_titulo))
        
        # Teléfono del negocio
        telefono_text = f"📞 {self.negocio_telefono}" if self.negocio_telefono else "📞 Sin teléfono registrado"
        elementos.append(Paragraph(telefono_text, estilo_telefono))
        
        # Fecha del reporte
        fecha_actual = datetime.now().strftime("%d de %B de %Y, %H:%M")
        elementos.append(Paragraph(f"📅 Reporte generado: {fecha_actual}", estilo_fecha))
        
        # Espacio
        elementos.append(Spacer(1, 0.5*cm))
        
        # ============================================
        # 2. TÍTULO DEL REPORTE (Centro)
        # ============================================
        
        if tipo_reporte == 'activos':
            titulo = "📊 REPORTE DE CONTRATOS ACTIVOS"
        elif tipo_reporte == 'vencidos':
            titulo = "📊 REPORTE DE CONTRATOS VENCIDOS"
        else:
            titulo = "📊 REPORTE GENERAL DE CONTRATOS"
        
        elementos.append(Paragraph(titulo, estilo_titulo_reporte))
        
        # Subtítulo con estadísticas
        total = len(contratos)
        activos = len([c for c in contratos if c.get('estado') == 'activo'])
        vencidos = len([c for c in contratos if c.get('estado') == 'vencido'])
        
        subtitulo_text = f"Total: {total} contratos | Activos: {activos} | Vencidos: {vencidos}"
        elementos.append(Paragraph(subtitulo_text, estilo_subtitulo))
        
        # Espacio
        elementos.append(Spacer(1, 0.5*cm))
        
        # ============================================
        # 3. TABLA DE CONTRATOS
        # ============================================
        
        if contratos:
            # Preparar datos para la tabla
            tabla_datos = []
            
            # Encabezados
            headers = [
                "N° Contrato",
                "Empresa / TCP / MIPYME",
                "Fecha Inicio",
                "Fecha Fin",
                "Gastos ($)",
                "Estado"
            ]
            tabla_datos.append(headers)
            
            # Filas de datos
            for c in contratos:
                # Calcular gastos (monto del contrato)
                gastos = c.get('monto', 0)
                
                # Estado con formato
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
            
            # Crear tabla con estilo
            tabla = Table(tabla_datos, colWidths=[2.2*cm, 5*cm, 2.5*cm, 2.5*cm, 2.5*cm, 2.8*cm])
            
            # Estilo de la tabla
            tabla.setStyle(TableStyle([
                # Encabezados
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#6c3ce0')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
                ('TOPPADDING', (0, 0), (-1, 0), 8),
                
                # Filas de datos
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 9),
                ('ALIGN', (0, 1), (0, -1), 'CENTER'),  # N° Contrato centrado
                ('ALIGN', (4, 1), (4, -1), 'RIGHT'),   # Gastos a la derecha
                ('ALIGN', (5, 1), (5, -1), 'CENTER'),  # Estado centrado
                ('TOPPADDING', (0, 1), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
                
                # Bordes
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cccccc')),
                ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#999999')),
                
                # Filas alternadas
                ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f9f9f9')),
                ('BACKGROUND', (0, 2), (-1, -1), colors.white),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor('#f9f9f9'), colors.white]),
            ]))
            
            elementos.append(tabla)
            
            # ============================================
            # 4. RESUMEN FINAL
            # ============================================
            
            elementos.append(Spacer(1, 0.5*cm))
            
            # Calcular total de gastos
            total_gastos = sum(c.get('monto', 0) for c in contratos)
            
            # Estilo para el resumen
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
            
            # Firma
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
            # Sin contratos
            estilo_vacio = ParagraphStyle(
                'Vacio',
                parent=styles['Normal'],
                fontSize=12,
                textColor=colors.HexColor('#888888'),
                alignment=TA_CENTER,
                spaceBefore=20
            )
            elementos.append(Paragraph("No hay contratos para mostrar", estilo_vacio))
        
        # ============================================
        # 5. PIE DE PÁGINA
        # ============================================
        
        # Estilo para el pie
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
        
        # Generar PDF
        doc.build(elementos)
        
        # Obtener el PDF como bytes
        pdf_bytes = self.buffer.getvalue()
        self.buffer.close()
        
        return pdf_bytes
