import os
import json
import pandas as pd
import logging as log

from tkinter import *
from tkinter import ttk
from tkinter import filedialog
from tkinter import messagebox
from tkinter import scrolledtext

log.basicConfig(
    filename = __file__[:-3] + '.log', 
    level = log.DEBUG, 
    format = '%(asctime)s | %(name)s | %(levelname)s | %(message)s'
)

class StatusBar(Frame):   
    def __init__(self, master):
        Frame.__init__(self, master)
        self.variable = StringVar()        
        self.label = Label(self, anchor=W,
                           textvariable=self.variable,
                           font=('arial',12,'normal'))
        self.variable.set('Status Bar: Ready')
        self.label.pack(fill=X)        


class App(Tk):
    def __init__(self):
        super().__init__()
        # ventana
        window_height = 620
        window_width = 1150
        self.title('Parquet Viewer')
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        x_cordinate = int((screen_width/2) - (window_width/2))
        y_cordinate = int((screen_height/2) - (window_height/2))
        self.geometry("{}x{}+{}+{}".format(window_width, window_height, x_cordinate, y_cordinate))

        self.load_init_config()
        self.set_variables()
        self.create_widgets()

    def load_init_config(self):
        log.info("Configuración iniciada")

    def set_variables(self):
        self.var_path_parquet_file = StringVar(value='')
        self.var_tabla_ingesta = StringVar(value='')
        self.var_init = StringVar(value='')
        #self.var_init.trace('w',self.on_change_init)
        self.var_ambiente = StringVar(value='Todos')
        self.var_con_datamuestra = BooleanVar(value=True)
        self.var_encoding = StringVar(value='UTF-8')
        self.var_separador = StringVar(value='  |')
        self.var_con_cabecera = BooleanVar(value=True)
        self.var_ingestdate = BooleanVar(value=False)
        self.var_manual_partitions = StringVar(value='[]')
        self.var_manual_tags = StringVar(value='{}')
        self.var_sqs_dev = StringVar(value='')
        self.var_sqs_prd = StringVar(value='')
        self.var_s3_source_dev = StringVar(value='')
        self.var_s3_output_tmp_dev = StringVar(value='')
        self.var_s3_output_dev = StringVar(value='')
        self.var_s3_output_dm_dev = StringVar(value='')

        self.var_s3_source_prd = StringVar(value='')
        self.var_s3_output_tmp_prd = StringVar(value='')
        self.var_s3_output_prd = StringVar(value='')
        self.var_s3_output_dm_prd = StringVar(value='')

        self.var_db_output_dev = StringVar(value='')
        self.var_db_output_dm_dev = StringVar(value='')
        self.var_db_output_prd = StringVar(value='')
        self.var_db_output_dm_prd = StringVar(value='')

        self.var_mcp_dev = {}
        self.var_mcp_prd = {}

        self.var_extra_atts_dev = {}
        self.var_extra_atts_prd = {}

    # Funcion que selecciona la carpeta de la tabla
    def select_directory(self, event):
        root_dir = os.path.dirname(os.path.realpath(__file__)) + os.sep + 'ingestas'
        folder_selected = filedialog.askdirectory(title="Seleccione Carpeta de la Tabla", initialdir=root_dir)
        path_dir = str(folder_selected)
        if len(path_dir)>0:
            folder_name = path_dir.split('/')[-1] if path_dir.find('/') else path_dir.split(os.sep)[-1]
            self.var_tabla_ingesta.set(folder_name)

    # Funcion que selecciona un archivo parquet y guarda su path
    def select_parquet_file(self):
        root_dir = os.path.dirname(os.path.realpath(__file__)) + os.sep + 'ingestas'
        file_selected = filedialog.askopenfilename(title="Seleccione Archivo Parquet", initialdir=root_dir)
        path_file = str(file_selected)
        if len(path_file)>0:
            self.var_path_parquet_file.set(path_file)
            self.status_bar.variable.set('Espere un momento por favor...')
            self.mostrar_datos()

    def create_widgets(self):

        menubar = Menu(self)
        filemenu = Menu(menubar, tearoff=0)
        filemenu.add_command(label="Open Parquet", command=self.select_parquet_file)
        filemenu.add_command(label="Open CSV", command=self.select_parquet_file)
        filemenu.add_separator()
        filemenu.add_command(label="Save as CSV", command=self.select_parquet_file)
        filemenu.add_command(label="Save as Excel", command=self.select_parquet_file)
        filemenu.add_command(label="Save as Parquet", command=self.select_parquet_file)
        filemenu.add_separator()
        filemenu.add_command(label="Exit", command=self.cerrar_ventana)
        menubar.add_cascade(label="File", menu=filemenu)

        editmenu = Menu(menubar, tearoff=0)
        editmenu.add_command(label="Copy", command=self.select_parquet_file)
        editmenu.add_command(label="Find", command=self.select_parquet_file)
        editmenu.add_separator()
        editmenu.add_command(label="Replace", command=self.cerrar_ventana)
        menubar.add_cascade(label="Edit", menu=editmenu)

        toolsmenu = Menu(menubar, tearoff=0)
        toolsmenu.add_command(label="View Schema", command=self.select_parquet_file)
        toolsmenu.add_separator()
        toolsmenu.add_command(label="Edit Schema", command=self.cerrar_ventana)
        menubar.add_cascade(label="Tools", menu=toolsmenu)

        helpmenu = Menu(menubar, tearoff=0)
        helpmenu.add_command(label="Help Index", command=self.select_parquet_file)
        helpmenu.add_command(label="About us", command=self.select_parquet_file)
        menubar.add_cascade(label="Help", menu=helpmenu)

        self.config(menu=menubar)

        filter_frame = Frame(self)
        filter_frame.pack(padx = 5, pady = 5)

        self.where_label = Label(filter_frame, text = 'Where:', anchor=W, width = 22)
        self.where_label.grid(row = 0, column = 0)
        
        self.btn_aceptar = ttk.Button(filter_frame, text = 'Filtrar', width=10)
        self.btn_aceptar.grid(row = 0, column = 1)
        self.btn_aceptar.config(command = self.mostrar_datos)
        
        grid_frame = Frame(self, bd=1)
        grid_frame.pack(pady = 5, padx = 5)
        # expandir grid_frame verticalmente y horizontalmente todo el espacio disponible
        grid_frame.pack(fill = BOTH, expand = 1)

        #scrollbar
        game_scroll_y = Scrollbar(grid_frame)
        game_scroll_y.pack(side = RIGHT, fill = Y)

        game_scroll_x = Scrollbar(grid_frame, orient = 'horizontal')
        game_scroll_x.pack(side= BOTTOM, fill = X)

        self.grid_table = ttk.Treeview(grid_frame, yscrollcommand = game_scroll_y.set, xscrollcommand = game_scroll_x.set)
        self.grid_table.pack(expand = True, fill = BOTH)

        game_scroll_y.config(command=self.grid_table.yview)
        game_scroll_x.config(command=self.grid_table.xview)

        status_frame = Frame(self)
        status_frame.pack(pady = 5, padx = 5, fill = X)


        self.status_bar = StatusBar(status_frame)
        self.status_bar.grid(row = 5, columnspan = 2, sticky = W + E)

    def mostrar_sample(self):

        self.grid_table['columns'] = ('player_id', 'player_name', 'player_Rank', 'player_states', 'player_city')

        self.grid_table.column("#0", width=0,  stretch=NO)
        self.grid_table.column("player_id",anchor=CENTER, width=80)
        self.grid_table.column("player_name",anchor=CENTER,width=80)
        self.grid_table.column("player_Rank",anchor=CENTER,width=80)
        self.grid_table.column("player_states",anchor=CENTER,width=80)
        self.grid_table.column("player_city",anchor=CENTER,width=80)

        self.grid_table.heading("#0",text="",anchor=CENTER)
        self.grid_table.heading("player_id",text="Id",anchor=CENTER)
        self.grid_table.heading("player_name",text="Name",anchor=CENTER)
        self.grid_table.heading("player_Rank",text="Rank",anchor=CENTER)
        self.grid_table.heading("player_states",text="States",anchor=CENTER)
        self.grid_table.heading("player_city",text="States",anchor=CENTER)

        self.grid_table.insert(parent='',index='end',iid=0,text='',
        values=('1','Ninja','101','Oklahoma', 'Moore'))
        self.grid_table.insert(parent='',index='end',iid=1,text='',
        values=('2','Ranger','102','Wisconsin', 'Green Bay'))
        self.grid_table.insert(parent='',index='end',iid=2,text='',
        values=('3','Deamon','103', 'California', 'Placentia'))
        self.grid_table.insert(parent='',index='end',iid=3,text='',
        values=('4','Dragon','104','New York' , 'White Plains'))
        self.grid_table.insert(parent='',index='end',iid=4,text='',
        values=('5','CrissCross','105','California', 'San Diego'))
        self.grid_table.insert(parent='',index='end',iid=5,text='',
        values=('6','ZaqueriBlack','106','Wisconsin' , 'TONY'))

        self.grid_table.pack()

    def mostrar_datos(self):
        
        file_parquet = self.var_path_parquet_file.get()
        if len(file_parquet)>0:
            # read parquet file
            df = pd.read_parquet(file_parquet)
            if not df.empty:

                # Convierte a minusculas y reemplaza espacios por _
                #df.columns = df.columns.str.lower().str.replace(' ', '_')
                
                columns = df.columns
                print(columns)
            
                self.grid_table['columns'] = (*columns, )
                
                # format our column
                self.grid_table.column("#0", width=0,  stretch=NO)
                for c in columns:
                    self.grid_table.column(c, anchor=CENTER, width=80)

                self.grid_table.heading("#0", text="", anchor=CENTER)
                for c in columns:
                    self.grid_table.heading(c, text=c, anchor=CENTER)
                
                for index, row in df.iterrows():
                    values = [('' if row[c]==None else row[c]) for c in columns]
                    self.grid_table.insert(
                        parent='',
                        index='end',
                        iid=index, text='',
                        values=(*values,)
                    )

                self.grid_table.pack()

                self.status_bar.variable.set(f"Registros: {len(df)}")
            else:
                messagebox.showerror(message="El archivo no tiene datos para mostrar", title="Error")
        else:
            messagebox.showerror(message="Seleccione un archivo parquet", title="Error")
        
    
    def cerrar_ventana(self):
        answer = messagebox.askyesno(
            title='Cancelar', 
            message='¿Está seguro de cerrar la aplicación?'
        )
        if answer:
            self.destroy()

if __name__ == "__main__":
    app = App()
    log.info('###################')
    log.info('Aplicación iniciada')
    app.mainloop()
