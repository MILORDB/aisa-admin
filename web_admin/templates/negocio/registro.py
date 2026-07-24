@app.route('/api/negocio/registrar', methods=['POST'])
@login_required
def registrar_negocio():
    data = request.get_json()
    negocio_id = data.get('negocio_id')
    
    # Crear carpeta en la nube para el negocio
    from web_admin.storage import StorageManager
    storage = StorageManager()
    exito = storage.crear_carpeta_negocio(negocio_id)
    
    if exito:
        return jsonify({'success': True, 'message': 'Carpeta creada correctamente'})
    else:
        return jsonify({'error': 'Error creando carpeta'}), 500