from tkinter import *
from tkinter import ttk

def create_header_frame(parent):
    header_frame = Frame(parent)
    
    # Cajas de texto y selectores de filtros
    entry1 = Entry(header_frame)
    entry1.pack(side=LEFT, padx=10, pady=5)
    
    entry2 = Entry(header_frame)
    entry2.pack(side=LEFT, padx=10, pady=5)
    
    filter_selector = StringVar()
    filter_selector.set("Todos")
    filter_menu = OptionMenu(header_frame, filter_selector, "Todos", "Filtro1", "Filtro2", "Filtro3")
    filter_menu.pack(side=LEFT, padx=10, pady=5)
    
    # Botón
    button = Button(header_frame, text="Buscar", command=lambda: print("Búsqueda realizada"))
    button.pack(side=LEFT, padx=10, pady=5)
    
    return header_frame

def create_data_frame(parent):
    data_frame = Frame(parent)
    
    # Tabla o grid de datos (usando un widget Treeview como ejemplo)
    columns = ("Nombre", "Edad", "Correo")
    data_table = ttk.Treeview(data_frame, columns=columns, show="headings")
    
    for col in columns:
        data_table.heading(col, text=col)
        data_table.column(col, width=100)
        
    # Insertar datos de ejemplo
    data_table.insert("", "end", values=("Juan", "30", "juan@example.com"))
    data_table.insert("", "end", values=("María", "25", "maria@example.com"))
    data_table.insert("", "end", values=("Pedro", "28", "pedro@example.com"))
    
    data_table.pack(fill=BOTH, expand=True)
    
    return data_frame

def create_pagination_frame2(parent):
    pagination_frame = Frame(parent)
    
    # Etiqueta para mostrar el rango de registros mostrados
    range_label = Label(pagination_frame, text="Showing 11 to 15 of 50 entries")
    range_label.pack(side=LEFT, padx=10, pady=5)
    
    # Botones para cambiar de página (esto es solo un ejemplo visual)
    prev_page_button = Button(pagination_frame, text="<", command=lambda: print("Página anterior"))
    prev_page_button.pack(side=LEFT, padx=5, pady=5)
    
    page_numbers_label = Label(pagination_frame, text="1 2 3 4 5 6 7 ... 100")
    page_numbers_label.pack(side=LEFT, padx=5, pady=5)
    
    next_page_button = Button(pagination_frame, text=">", command=lambda: print("Página siguiente"))
    next_page_button.pack(side=LEFT, padx=5, pady=5)
    
    return pagination_frame

def create_pagination_frame3(parent):
    pagination_frame = Frame(parent)
    
    # Etiqueta para mostrar el rango de registros mostrados
    range_label = Label(pagination_frame, text="Showing 11 to 15 of 50 entries")
    range_label.pack(side=LEFT, padx=10, pady=5)
    
    # Función para cambiar de página (esto es solo un ejemplo visual)
    def change_page(page_number):
        print(f"Cambiando a la página {page_number}")
    
    # Botones para cambiar de página (esto es solo un ejemplo visual)
    prev_page_button = Button(pagination_frame, text="<", command=lambda: change_page("anterior"))
    prev_page_button.pack(side=LEFT, padx=5, pady=5)
    
    # Botones de número de página (1, 2, 3, ..., 100)
    for page_number in range(1, 101):
        if page_number == 1 or page_number == 100:
            # Mostrar el primer y último número de página como botones
            page_button = Button(pagination_frame, text=str(page_number), command=lambda n=page_number: change_page(n))
            page_button.pack(side=LEFT, padx=5, pady=5)
        elif page_number <= 7 or page_number >= 94:
            # Mostrar los números de página 2 a 7 y de 94 a 99 como botones
            page_button = Button(pagination_frame, text=str(page_number), command=lambda n=page_number: change_page(n))
            page_button.pack(side=LEFT, padx=5, pady=5)
        elif page_number == 8 or page_number == 93:
            # Mostrar los puntos suspensivos "..." entre el número 7 y 8, y entre 93 y 94
            page_label = Label(pagination_frame, text="...")
            page_label.pack(side=LEFT, padx=5, pady=5)
    
    next_page_button = Button(pagination_frame, text=">", command=lambda: change_page("siguiente"))
    next_page_button.pack(side=LEFT, padx=5, pady=5)
    
    return pagination_frame

def create_pagination_frame4(parent):
    pagination_frame = Frame(parent)
    
    # Etiqueta para mostrar el rango de registros mostrados
    range_label = Label(pagination_frame, text="Showing 11 to 15 of 50 entries")
    range_label.pack(side=LEFT, padx=10, pady=5)
    
    # Función para cambiar de página (esto es solo un ejemplo visual)
    def change_page(page_number):
        print(f"Cambiando a la página {page_number}")
    
    # Número de página actual (esto es solo un ejemplo visual)
    current_page = 1
    
    # Botones para cambiar de página (esto es solo un ejemplo visual)
    prev_page_button = Button(pagination_frame, text="<", command=lambda: change_page("anterior"))
    prev_page_button.pack(side=LEFT, padx=5, pady=5)
    
    # Botones de número de página (1, 2, 3, ..., 100)
    for page_number in range(1, 101):
        if page_number == 1 or page_number == 100:
            # Mostrar el primer y último número de página como botones
            page_label = Label(pagination_frame, text=str(page_number), padx=5, pady=5, relief=RAISED, bg="white")
        elif page_number <= 7 or page_number >= 94:
            # Mostrar los números de página 2 a 7 y de 94 a 99 como botones
            page_label = Label(pagination_frame, text=str(page_number), padx=5, pady=5, relief=RAISED, bg="white")
        elif page_number == 8 or page_number == 93:
            # Mostrar los puntos suspensivos "..." entre el número 7 y 8, y entre 93 y 94
            page_label = Label(pagination_frame, text="...", padx=5, pady=5)
        
        if page_number == current_page:
            # Aplicar sombreado o negrita al número de página actual
            page_label.config(font=("Helvetica", 12, "bold"))
        
        page_label.pack(side=LEFT)
    
    next_page_button = Button(pagination_frame, text=">", command=lambda: change_page("siguiente"))
    next_page_button.pack(side=LEFT, padx=5, pady=5)
    
    return pagination_frame

def create_pagination_frame(parent):
    pagination_frame = Frame(parent)

    # Número de registros mostrados y total
    records_label = Label(pagination_frame, text="Mostrando 3 de 9 registros")
    records_label.pack(side=LEFT, padx=10, pady=5)
    
    # Botones de paginación
    next_button = Button(pagination_frame, text="Next >", command=lambda: print("Página siguiente"))
    next_button.pack(side=RIGHT, padx=10, pady=5)

    page_label = Label(pagination_frame, text="1 / 3")
    page_label.pack(side=RIGHT, padx=10, pady=5)

    prev_button = Button(pagination_frame, text="< Back", command=lambda: print("Página anterior"))
    prev_button.pack(side=RIGHT, padx=10, pady=5)
    
    return pagination_frame

def create_status_bar_frame(parent):
    status_bar_frame = Frame(parent)
    
    # Barra de progreso (alineado a la izquierda)
    progress_bar = ttk.Progressbar(status_bar_frame, orient="horizontal", length=120, mode="indeterminate")
    progress_bar.pack(side=LEFT, padx=10, pady=5)
    progress_bar.start()
     
    # Barra de estado (alineado a la derecha)
    status_label = Label(status_bar_frame, text="Estado: OK")
    status_label.pack(side=RIGHT, padx=10, pady=5)
    
    return status_bar_frame

def main():
    root = Tk()
    root.title("Ejemplo de Organización con Frames")

    # Crear los frames para cada sección
    header_frame = create_header_frame(root)
    data_frame = create_data_frame(root)
    pagination_frame = create_pagination_frame(root)
    status_bar_frame = create_status_bar_frame(root)

    # Organizar los frames en la ventana principal
    header_frame.pack(side=TOP, fill=X)
    data_frame.pack(side=TOP, fill=BOTH, expand=True)
    pagination_frame.pack(side=TOP, fill=X)
    status_bar_frame.pack(side=BOTTOM, fill=X)

    root.mainloop()

if __name__ == "__main__":
    main()
