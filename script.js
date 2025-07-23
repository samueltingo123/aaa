class IAMinimarketChat {
    constructor() {
        this.initializeElements();
        this.initializeTheme();
        this.initializeEventListeners();
        this.initializeChat();
    }

    initializeElements() {
        // Elementos del DOM
        this.chatMessages = document.getElementById('chatMessages');
        this.userInput = document.getElementById('userInput');
        this.sendButton = document.getElementById('sendButton');
        this.typingIndicator = document.getElementById('typingIndicator');
        this.themeToggle = document.getElementById('themeToggle');
        this.menuToggle = document.getElementById('mobileMenuToggle');
        this.mobileMenu = document.getElementById('navMenu');
        this.mobileMenuOverlay = document.getElementById('mobileMenuOverlay');
        
        // Elementos adicionales para móvil
        this.mobileThemeToggle = document.getElementById('mobileThemeToggle');
    }

    initializeTheme() {
        // Cargar tema guardado o usar el del sistema
        const savedTheme = localStorage.getItem('theme');
        const systemPrefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
        
        if (savedTheme) {
            document.documentElement.setAttribute('data-theme', savedTheme);
        } else if (systemPrefersDark) {
            document.documentElement.setAttribute('data-theme', 'dark');
        }
    }

    initializeEventListeners() {
        // Botón de enviar
        this.sendButton.addEventListener('click', () => this.sendMessage());
        
        // Enter para enviar (Shift+Enter para nueva línea)
        this.userInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });

        // Auto-resize del textarea
        this.userInput.addEventListener('input', () => {
            this.autoResizeTextarea();
        });

        // Toggle de tema (desktop)
        if (this.themeToggle) {
            this.themeToggle.addEventListener('click', () => {
                this.toggleTheme();
            });
        }

        // Toggle de tema (móvil)
        if (this.mobileThemeToggle) {
            this.mobileThemeToggle.addEventListener('click', () => {
                this.toggleTheme();
            });
        }

        // Toggle del menú móvil
        if (this.menuToggle) {
            this.menuToggle.addEventListener('click', () => {
                this.toggleMobileMenu();
            });
        }

        // Cerrar menú al hacer click en overlay
        if (this.mobileMenuOverlay) {
            this.mobileMenuOverlay.addEventListener('click', () => {
                this.closeMobileMenu();
            });
        }

        // Prevenir scroll cuando el menú está abierto
        window.addEventListener('resize', () => {
            if (window.innerWidth > 768) {
                this.closeMobileMenu();
            }
        });
    }

    initializeChat() {
        // Mensaje de bienvenida ya está en el HTML
        this.scrollToBottom();
    }

    toggleTheme() {
        const currentTheme = document.documentElement.getAttribute('data-theme');
        const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
        
        document.documentElement.setAttribute('data-theme', newTheme);
        localStorage.setItem('theme', newTheme);
        
        // Animación suave
        document.documentElement.style.transition = 'background-color 0.3s ease, color 0.3s ease';
    }

    toggleMobileMenu() {
        if (this.mobileMenu && this.mobileMenuOverlay && this.menuToggle) {
            this.mobileMenu.classList.add('active');
            this.mobileMenuOverlay.classList.add('active');
            this.menuToggle.classList.add('active');
            document.body.style.overflow = 'hidden';
        }
    }

    closeMobileMenu() {
        if (this.mobileMenu && this.mobileMenuOverlay && this.menuToggle) {
            this.mobileMenu.classList.remove('active');
            this.mobileMenuOverlay.classList.remove('active');
            this.menuToggle.classList.remove('active');
            document.body.style.overflow = '';
        }
    }

    autoResizeTextarea() {
        this.userInput.style.height = 'auto';
        this.userInput.style.height = Math.min(this.userInput.scrollHeight, 96) + 'px';
    }

    async sendMessage() {
        const message = this.userInput.value.trim();
        if (!message) return;

        // Deshabilitar el botón de enviar
        this.sendButton.disabled = true;
        
        // Añadir mensaje del usuario
        this.addMessage(message, 'user');
        
        // Limpiar input
        this.userInput.value = '';
        this.autoResizeTextarea();
        
        // Mostrar indicador de escritura
        this.showTypingIndicator();

        try {
            // Enviar mensaje al servidor
            const response = await fetch('/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ message })
            });

            const data = await response.json();
            
            // Ocultar indicador de escritura
            this.hideTypingIndicator();
            
            // Añadir respuesta de la IA
            this.addAIMessage(data.response, data);
            
        } catch (error) {
            console.error('Error:', error);
            this.hideTypingIndicator();
            this.addMessage('Lo siento, ocurrió un error al procesar tu solicitud. Por favor, intenta de nuevo.', 'ai');
        } finally {
            // Habilitar el botón de enviar
            this.sendButton.disabled = false;
            this.userInput.focus();
        }
    }

    addMessage(text, sender) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${sender}`;
        
        // Avatar
        const avatarDiv = document.createElement('div');
        avatarDiv.className = 'message-avatar';
        
        if (sender === 'user') {
            avatarDiv.innerHTML = `
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                    <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
                    <circle cx="12" cy="7" r="4"/>
                </svg>
            `;
        } else {
            avatarDiv.innerHTML = `
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                    <path d="M12 2L2 7v10c0 5.55 3.84 10.74 9 12 5.16-1.26 9-6.45 9-12V7l-10-5z"/>
                </svg>
            `;
        }
        
        // Contenido del mensaje
        const contentDiv = document.createElement('div');
        contentDiv.className = 'message-content';
        contentDiv.textContent = text;
        
        messageDiv.appendChild(avatarDiv);
        messageDiv.appendChild(contentDiv);
        
        this.chatMessages.appendChild(messageDiv);
        this.scrollToBottom();
    }

    addAIMessage(text, data) {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message ai';
        
        // Avatar
        const avatarDiv = document.createElement('div');
        avatarDiv.className = 'message-avatar';
        avatarDiv.innerHTML = `
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                <path d="M12 2L2 7v10c0 5.55 3.84 10.74 9 12 5.16-1.26 9-6.45 9-12V7l-10-5z"/>
            </svg>
        `;
        
        // Contenido del mensaje
        const contentDiv = document.createElement('div');
        contentDiv.className = 'message-content';
        
        // Formatear la respuesta según el tipo
        if (data && data.tipo_respuesta) {
            contentDiv.innerHTML = this.formatResponse(text, data);
        } else {
            contentDiv.innerHTML = this.formatGeneralResponse(text);
        }
        
        messageDiv.appendChild(avatarDiv);
        messageDiv.appendChild(contentDiv);
        
        this.chatMessages.appendChild(messageDiv);
        this.scrollToBottom();
    }

    formatResponse(text, data) {
        // Si es una respuesta conversacional, formatear de manera simple
        if (data.tipo_respuesta === 'conversacional') {
            return this.formatConversationalResponse(text);
        }
        
        // Si es una consulta de productos simple o compleja
        if (data.tipo_respuesta === 'busqueda_producto' || 
            data.tipo_respuesta === 'consulta_compleja') {
            return this.formatProductResponse(text, data);
        }
        
        // Si es un error
        if (data.tipo_respuesta === 'error_producto' || 
            data.tipo_respuesta === 'error_sql' || 
            data.tipo_respuesta === 'error_sistema') {
            return this.formatErrorResponse(text, data);
        }
        
        // Respuesta general
        return this.formatGeneralResponse(text);
    }

    formatConversationalResponse(text) {
        // Para respuestas conversacionales, mantener formato simple pero atractivo
        let formatted = text
            // Negrita
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            // Saltos de línea
            .replace(/\n/g, '<br>')
            // Emojis con tamaño ligeramente mayor
            .replace(/(😊|👋|🛒|✨|🎯|💡|🤝|🎉|😄|🤔|💪|🌟|👍|🏪|🔍|📦|💰|🍺|🥤)/g, '<span style="font-size: 1.3em;">$1</span>')
            // Listas
            .replace(/^- /gm, '• ')
            .replace(/^\d+\. /gm, '<br>• ');
        
        return `<div class="conversational-response">${formatted}</div>`;
    }

    formatErrorResponse(text, data) {
        let icon = '❌';
        if (data.tipo_respuesta === 'error_producto') {
            icon = '🔍';
        } else if (data.tipo_respuesta === 'error_sistema') {
            icon = '⚠️';
        }
        
        return `
            <div class="error-response">
                <div class="error-icon">${icon}</div>
                <div class="error-message">${this.formatGeneralResponse(text)}</div>
            </div>
        `;
    }

    formatProductResponse(text, data) {
        let html = '';
        
        // Contexto de búsqueda para consultas simples
        if (data.producto_buscado && data.tipo_respuesta === 'busqueda_producto') {
            html += `
            `;
        }
        
        // Para consultas complejas, mostrar el tipo
        if (data.tipo_respuesta === 'consulta_compleja') {
            html += `
                <div class="search-context mb-2">
                    <strong>📊 Consulta compleja</strong>
                </div>
            `;
        }
        
        // Parsear productos del texto
        const productos = this.parseProductsFromText(text);
        
        if (productos.length > 0) {
            html += '<div class="product-grid">';
            
            productos.forEach(producto => {
                const isAvailable = producto.stock !== 'Sin stock - Temporalmente agotado' && 
                                  producto.stock !== '0 unidades disponibles' &&
                                  !producto.stock.includes('agotado') &&
                                  !producto.stock.includes('Agotado');
                                  
                html += `
                    <div class="product-card">
                        <div class="product-header">
                            <h4 class="product-name">${producto.nombre}</h4>
                            <span class="product-status ${isAvailable ? 'status-available' : 'status-unavailable'}">
                                ${isAvailable ? '✅ Disponible' : '❌ Sin stock'}
                            </span>
                        </div>
                        <div class="product-details">
                `;
                
                if (producto.stock) {
                    html += `
                        <div class="detail-row">
                            <span class="detail-label">📦 Stock:</span>
                            <span class="detail-value">${producto.stock}</span>
                        </div>
                    `;
                    
                    // Agregar advertencias si el stock es bajo
                    if (producto.stockWarning) {
                        html += `
                            <div class="detail-row">
                                <span class="detail-label">⚠️</span>
                                <span class="detail-value" style="color: var(--warning-color);">${producto.stockWarning}</span>
                            </div>
                        `;
                    }
                }
                
                if (producto.presentaciones && producto.presentaciones.length > 0) {
                    html += `
                        <div class="detail-row">
                            <span class="detail-label">💰 Presentaciones:</span>
                            <span class="detail-value">${producto.presentaciones.length}</span>
                        </div>
                    `;
                    
                    producto.presentaciones.forEach(pres => {
                        html += `
                            <div class="detail-row">
                                <span class="detail-label" style="margin-left: 1rem;">${pres.nombre}:</span>
                                <span class="detail-value">${pres.precio}</span>
                            </div>
                        `;
                    });
                }
                
                // Información adicional para consultas complejas
                if (producto.infoAdicional) {
                    producto.infoAdicional.forEach(info => {
                        html += `
                            <div class="detail-row">
                                <span class="detail-label">${info.label}:</span>
                                <span class="detail-value">${info.value}</span>
                            </div>
                        `;
                    });
                }
                
                html += `
                        </div>
                    </div>
                `;
            });
            
            html += '</div>';
        } else {
            // Si no se pueden parsear productos, mostrar el texto formateado
            html += this.formatGeneralResponse(text);
        }
        
        // Resumen de resultados
        if (data.total_resultados !== undefined) {
            html += `
            `;
        }
        
        return html;
    }

    formatGeneralResponse(text) {
        // Formatear respuesta general con mejoras visuales
        let formatted = text
            // Negrita
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            // Saltos de línea
            .replace(/\n/g, '<br>')
            // Emojis con estilos
            .replace(/✅/g, '<span style="color: var(--success-color);">✅</span>')
            .replace(/❌/g, '<span style="color: var(--error-color);">❌</span>')
            .replace(/📦/g, '<span style="color: var(--warning-color);">📦</span>')
            .replace(/💰/g, '<span style="color: var(--success-color);">💰</span>')
            .replace(/🔍/g, '<span style="color: var(--info-color);">🔍</span>')
            .replace(/📊/g, '<span style="color: var(--primary-color);">📊</span>')
            .replace(/⚠️/g, '<span style="color: var(--warning-color);">⚠️</span>')
            .replace(/🏆/g, '<span style="color: #FFD700;">🏆</span>')
            .replace(/🍺/g, '<span style="font-size: 1.2em;">🍺</span>')
            .replace(/🛒/g, '<span style="font-size: 1.2em;">🛒</span>')
            .replace(/✨/g, '<span style="font-size: 1.2em;">✨</span>')
            // Listas numeradas
            .replace(/^\d+\.\s/gm, '<br>• ')
            // Líneas divisorias
            .replace(/─{3,}/g, '<hr style="margin: 1rem 0; border: none; border-top: 1px solid var(--border-color);">');
        
        return `<div>${formatted}</div>`;
    }

    parseProductsFromText(text) {
        const productos = [];
        const lines = text.split('\n');
        let currentProduct = null;
        
        for (let i = 0; i < lines.length; i++) {
            const line = lines[i].trim();
            
            // Detectar inicio de producto (✅ o ❌ seguido de nombre en negrita)
            if ((line.includes('✅') || line.includes('❌')) && line.includes('**')) {
                // Si ya había un producto en proceso, guardarlo
                if (currentProduct) {
                    productos.push(currentProduct);
                }
                
                // Extraer nombre del producto
                const nombreMatch = line.match(/\*\*(.*?)\*\*/);
                const nombre = nombreMatch ? nombreMatch[1] : line.replace(/[✅❌]/g, '').trim();
                
                currentProduct = {
                    nombre: nombre,
                    status: line.includes('✅') ? 'disponible' : 'no_disponible',
                    stock: '',
                    stockWarning: '',
                    presentaciones: [],
                    infoAdicional: []
                };
            }
            
            // Detectar stock
            else if (line.includes('📦') && currentProduct) {
                // Buscar patrones de stock
                const stockMatch = line.match(/📦\s*(.+)/);
                if (stockMatch) {
                    currentProduct.stock = stockMatch[1].trim();
                    
                    // Verificar si el stock indica "Sin stock"
                    if (currentProduct.stock.toLowerCase().includes('sin stock') || 
                        currentProduct.stock.toLowerCase().includes('agotado')) {
                        currentProduct.status = 'no_disponible';
                    }
                }
            }
            
            // Detectar advertencias (⚠️)
            else if (line.includes('⚠️') && currentProduct) {
                const warningMatch = line.match(/⚠️\s*(.+)/);
                if (warningMatch) {
                    currentProduct.stockWarning = warningMatch[1].trim();
                }
            }
            
            // Detectar presentaciones (líneas numeradas)
            else if (line.match(/^\d+\.\s/) && currentProduct) {
                const parts = line.split(' - ');
                if (parts.length >= 2) {
                    currentProduct.presentaciones.push({
                        nombre: parts[0].replace(/^\d+\.\s/, '').trim(),
                        precio: parts[1].trim()
                    });
                }
            }
            
            // Detectar información adicional (🏆 para ventas, etc.)
            else if (line.includes('🏆') && currentProduct) {
                const infoMatch = line.match(/🏆\s*(.+)/);
                if (infoMatch) {
                    currentProduct.infoAdicional.push({
                        label: '🏆 Ventas',
                        value: infoMatch[1].trim()
                    });
                }
            }
            
            // Detectar líneas con formato "💰 Presentaciones:"
            else if (line.includes('💰') && line.includes('Presentaciones:') && currentProduct) {
                // Esta línea solo indica que siguen las presentaciones
                continue;
            }
            
            // Detectar precio directo (💰 Precio:)
            else if (line.includes('💰') && line.includes('Precio:') && currentProduct) {
                const precioMatch = line.match(/💰\s*Precio:\s*(.+)/);
                if (precioMatch && currentProduct.presentaciones.length === 0) {
                    currentProduct.presentaciones.push({
                        nombre: 'Principal',
                        precio: precioMatch[1].trim()
                    });
                }
            }
            
            // Detectar stock directo (📊 Stock:)
            else if (line.includes('📊') && line.includes('Stock:') && currentProduct) {
                const stockMatch = line.match(/📊\s*Stock:\s*(.+)/);
                if (stockMatch) {
                    currentProduct.stock = stockMatch[1].trim();
                }
            }
        }
        
        // Agregar el último producto si existe
        if (currentProduct) {
            productos.push(currentProduct);
        }
        
        return productos;
    }

    showTypingIndicator() {
        this.typingIndicator.classList.add('active');
        this.scrollToBottom();
    }

    hideTypingIndicator() {
        this.typingIndicator.classList.remove('active');
    }

    scrollToBottom() {
        // Añadir un pequeño retraso para asegurar que el DOM se actualice
        setTimeout(() => {
            this.chatMessages.scrollTop = this.chatMessages.scrollHeight;
        }, 100);
    }
}

// Inicializar la aplicación cuando el DOM esté listo
document.addEventListener('DOMContentLoaded', () => {
    const app = new IAMinimarketChat();
    
    // Agregar algunos ejemplos de preguntas rápidas
    const quickQuestions = [
        "¿Tienes cerveza Corona?",
        "¿Qué productos tienen poco stock?",
        "Top 10 más vendidos",
        "¿Cuánto cuesta la Pepsi?",
        "¿Cuál es la cerveza más barata?",
        "¿Qué productos no tienen stock?",
        "¿Qué productos valen menos de 20 lempiras?",
        "Hola, ¿cómo estás?",
        "¿Qué puedes hacer?",
        "Cuéntame un chiste"
    ];
    
    // Función para agregar botones de preguntas rápidas (opcional)
    window.askQuickQuestion = (question) => {
        app.userInput.value = question;
        app.sendMessage();
    };
});

// Registrar Service Worker para funcionalidad offline (opcional)d
if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
        navigator.serviceWorker.register('/sw.js').catch(() => {
            // Service worker registration failed
        });
    });
}
