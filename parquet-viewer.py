import os
import json
import pandas as pd
import logging as log

from tkinter import *
from tkinter import ttk
from tkinter import filedialog
from tkinter import messagebox
from tkinter import scrolledtext

# General variables
var_path_data_file = ''
var_data_table = None
var_data_frame = None

# GUI variables
var_gui_status = None
var_gui_progress_bar = None

# Logging configuration
log.basicConfig(
    filename = __file__[:-3] + '.log', 
    level = log.DEBUG, 
    format = '%(asctime)s | %(name)s | %(levelname)s | %(message)s'
)

def event_modal_select_file():
    root_dir = os.path.dirname(os.path.realpath(__file__)) + os.sep
    file_selected = filedialog.askopenfilename(title="Seleccione Archivo", initialdir=root_dir)
    path_file = str(file_selected)
    if len(path_file)>0:
        global var_path_data_file
        var_path_data_file = path_file
        var_gui_status.set(f"Leyendo: {path_file}")
        # obtener el nombre del archivo sin directorios
        file_name = os.path.basename(path_file)
        log.info(f"Leyendo: {file_name}")

        event_start_progress_bar()
        proc_load_show_data()
        event_stop_progress_bar()
        var_gui_status.set(f"Archivo: {file_name}")

def action_close_window():
    answer = messagebox.askyesno(
        title='Cancelar', 
        message='¿Está seguro de cerrar la aplicación?'
    )
    if answer:
        ttk.destroy()

def event_start_progress_bar():
    var_gui_progress_bar.start()
    var_gui_progress_bar.pack()

def event_stop_progress_bar():
    var_gui_progress_bar.stop()
    var_gui_progress_bar.pack_forget()


def proc_load_show_data():
    
    file_path = var_path_data_file
    if len(file_path)>0:
        # read parquet file
        df = pd.DataFrame()
        if file_path.endswith('.parquet'):
            df = pd.read_parquet(file_path)
            log.info(f"Archivo parquet leído: {file_path}")
            log.info(f"Registros: {len(df)}")
        elif file_path.endswith('.csv'):
            df = pd.read_csv(file_path)
            log.info(f"Archivo csv leído: {file_path}")
            log.info(f"Registros: {len(df)}")
        else:
            log.error(f"El archivo no tiene un formato válido, se acepta archivos .parquet y .csv")
            messagebox.showerror(message="El archivo no tiene un formato válido, se acepta archivos .parquet y .csv", title="Error")
        
        if not df.empty:
            global var_data_frame
            var_data_frame = df
            # Convierte a minusculas y reemplaza espacios por _
            #df.columns = df.columns.str.lower().str.replace(' ', '_')
            
            columns = list(df.columns)
            log.info(f"Columnas: {columns}")

            global var_data_table
            # clear table
            for i in var_data_table.get_children():
                var_data_table.delete(i)
            
            var_data_table['columns'] = (*columns, ) #(c for c in columns) #(*columns, )
            
            # format our column
            var_data_table.column("#0", width=0,  stretch=NO)
            for c in columns:
                var_data_table.column(c, anchor=CENTER, width=80)

            var_data_table.heading("#0", text="", anchor=CENTER)
            for c in columns:
                var_data_table.heading(c, text=c, anchor=CENTER)
            
            for index, row in df.iterrows():
                values = [('' if row[c]==None else row[c]) for c in columns]
                var_data_table.insert(
                    parent='',
                    index='end',
                    iid=index, text='',
                    values=(*values,)
                )

            var_data_table.pack()

            #self.status_bar.variable.set(f"Registros: {len(df)}")
        else:
            messagebox.showerror(message="El archivo no tiene datos para mostrar", title="Error")
    else:
        messagebox.showerror(message="Seleccione un archivo", title="Error")


def create_menubar(parent):
    menubar = Menu(parent)
    filemenu = Menu(menubar, tearoff=0)
    filemenu.add_command(label="Open Parquet", command=event_modal_select_file)
    filemenu.add_command(label="Open CSV", command=event_modal_select_file)
    filemenu.add_separator()
    filemenu.add_command(label="Save as CSV", command=event_modal_select_file)
    filemenu.add_command(label="Save as Excel", command=event_modal_select_file)
    filemenu.add_command(label="Save as Parquet", command=event_modal_select_file)
    filemenu.add_separator()
    filemenu.add_command(label="Exit", command=action_close_window)
    menubar.add_cascade(label="File", menu=filemenu)

    editmenu = Menu(menubar, tearoff=0)
    editmenu.add_command(label="Copy", command=event_modal_select_file)
    editmenu.add_command(label="Find", command=event_modal_select_file)
    editmenu.add_separator()
    editmenu.add_command(label="Replace", command=action_close_window)
    menubar.add_cascade(label="Edit", menu=editmenu)

    toolsmenu = Menu(menubar, tearoff=0)
    toolsmenu.add_command(label="View Schema", command=event_modal_select_file)
    toolsmenu.add_separator()
    toolsmenu.add_command(label="Edit Schema", command=action_close_window)
    menubar.add_cascade(label="Tools", menu=toolsmenu)

    helpmenu = Menu(menubar, tearoff=0)
    helpmenu.add_command(label="Help Index", command=event_modal_select_file)
    helpmenu.add_command(label="About us", command=event_modal_select_file)
    menubar.add_cascade(label="Help", menu=helpmenu)

    return menubar

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
    global var_data_table
    var_data_table = ttk.Treeview(data_frame, columns=columns, show="headings")
    
    for col in columns:
        var_data_table.heading(col, text=col)
        var_data_table.column(col, width=100)
        
    # Insertar datos de ejemplo
    var_data_table.insert("", "end", values=("Juan", "30", "juan@example.com"))
    var_data_table.insert("", "end", values=("María", "25", "maria@example.com"))
    var_data_table.insert("", "end", values=("Pedro", "28", "pedro@example.com"))
    
    var_data_table.pack(fill=BOTH, expand=True)
    
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
    global var_gui_progress_bar
    var_gui_progress_bar = ttk.Progressbar(status_bar_frame, orient="horizontal", length=120, mode="indeterminate")
    var_gui_progress_bar.pack(side=LEFT, padx=10, pady=5)
    #var_gui_progress_bar.start()
    var_gui_progress_bar.pack_forget()
     
    # Barra de estado (alineado a la derecha)
    global var_gui_status
    var_gui_status = StringVar(value="Estado: OK")
    status_label = Label(status_bar_frame, text="Estado: OK", textvariable=var_gui_status)
    status_label.pack(side=RIGHT, padx=10, pady=5)
    
    return status_bar_frame

def main():
    root = Tk()
    root.title("Parquet Viewer and Utils - 2024")

    # Crear los frames para cada sección
    menubar = create_menubar(root)
    root.config(menu=menubar)
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
