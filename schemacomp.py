VERSION = "1.0"

print("Schemacomp v"+VERSION+" (c) 2024 Enderbyte Programs, all rights reserved.")

import pandas
import cursesplus
import pymssql
import pymysql
import curses
import enum


def connectionstring2dict(conn:str) -> dict[str,str]:
    res = {}
    for kv in conn.split(";"):
        if kv.strip() == "":
            continue
        k = kv.split("=")[0]
        v = kv.split("=")[1]

        res[k.lower()] = v
    return res

class ConnectionTypes(enum.Enum):
    MSSQL = 0
    MYSQL = 1

class ConnectionSpec:
    loc:str
    db:str
    user:str
    password:str
    ctype:ConnectionTypes
    def __init__(self,l:str,d:str,u:str,p:str,t:ConnectionTypes,port:int|None):
        self.loc = l
        self.db = d
        self.user = u
        self.password = p
        self.ctype = t
        self.portno = port
        if (port is None):
            if t == ConnectionTypes.MYSQL:
                self.portno = 3306
            else:
                self.portno = 1433

    def run_query(self,query:str) -> list[dict]:
        final:list[dict] = []
        if self.ctype == ConnectionTypes.MSSQL:
            #MS db
            conn = pymssql.connect(self.loc, self.user, self.password, self.db)
            cursor = conn.cursor(as_dict=True)

            cursor.execute(query)
            for row in cursor:
                final.append(row)

            conn.close()
        elif self.ctype == ConnectionTypes.MYSQL:
            connection = pymysql.connect(host=self.loc,
                             user=self.user,
                             password=self.password,
                             database=self.db,
                             cursorclass=pymysql.cursors.DictCursor,
                             port=self.portno)

            with connection:

                with connection.cursor() as cursor:
                    # Read a single record
                    cursor.execute(query)
                    for row in cursor.fetchall():
                        final.append(row)

        return final

    def test_connection(self) -> bool:
        try:
            if self.ctype == ConnectionTypes.MSSQL:
                #MS db
                conn = pymssql.connect(self.loc, self.user, self.password, self.db)

                conn.close()
            elif self.ctype == ConnectionTypes.MYSQL:
                connection = pymysql.connect(host=self.loc,
                                user=self.user,
                                password=self.password,
                                database=self.db,
                                cursorclass=pymysql.cursors.DictCursor)

                connection.close()
        except:
            return False

        return True

    def uf_create(stdscr):
        """User friendly create"""
        while True:
            dbop = cursesplus.coloured_option_menu(stdscr,["MySQL","MSSQL/Sql Server"],"Please select your database type")
            if dbop == 0:
                ctype = ConnectionTypes.MYSQL
            elif dbop == 1:
                ctype = ConnectionTypes.MSSQL
            conmethod = cursesplus.coloured_option_menu(stdscr,["Single fields","Connection String"],"How would you like to connect to this database?",footer="Use single fields to input username, password, etc one by one")
            if conmethod == 0:

                loc = cursesplus.cursesinput(stdscr,"What is the server address? (Don't include the port number)")
                if cursesplus.messagebox.askyesno(stdscr,["Is the database on a non standard port? (Not 3306 or 1433)"]):
                    pn = cursesplus.numericinput(stdscr,"Input the port number",maximum=65535)
                else:
                    pn = None
                db = cursesplus.cursesinput(stdscr,"What is the database name you want to look for?")
                usr = cursesplus.cursesinput(stdscr,"What is the username? (Should have read permissions for INFORMATION SCHEMA)")
                pwd = cursesplus.cursesinput(stdscr,"What is the password for"+usr+"?",passwordchar="*")

            elif conmethod == 1:
                result = connectionstring2dict(cursesplus.cursesinput(stdscr,"Paste in the full connection string"))
                #cursesplus.textview(stdscr,text=str(result))
                if dbop == 0:
                    loc = result["server"]
                    db = result["database"]
                    usr = result["uid"]
                    pwd = result["pwd"]
                    if "port" in result:
                        pn = int(result["port"])
                    else:
                        pn = None
                elif dbop == 1:
                    loc = result["server"]
                    db = result['initial catalog']
                    usr = result['user id']
                    pwd = result['password']
                    if len(loc.split(",")) > 1:
                        pn = int(loc.split(",")[1])
                        loc = loc.split(",")[0]
                    else:
                        pn = None

            cursesplus.displaymsg(stdscr,["Testing connection..."],False)
            output = ConnectionSpec(loc,db,usr,pwd,ctype,pn)
            if output.test_connection():
                cursesplus.messagebox.showinfo(stdscr,["Connection established."])
                return output
            else:
                cursesplus.messagebox.showerror(stdscr,["Failed to connect. Please try again."])

def find_matching_column(haystack,needle) -> dict|None:
    #Descriptive naming!
    for d in haystack:
        if d["TABLE_SCHEMA"]+"."+d["TABLE_NAME"]+"."+d["COLUMN_NAME"] == needle:
            return d
    return None

def main(stdscr):
    cursesplus.displaymsg(stdscr,[
        "===== SCHEMACOMP =====",
        "= COMPARE SQL SCHEMA =",
        "======================",
        "How it works:",
        "On the next screen you will be prompted for two servers.",
        "A report will be made about how the",
        "second server differs from the first one.",
        "Make sure to take that into account","when you choose the server order."
    ])
    cursesplus.messagebox.showinfo(stdscr,["Let's being by establishing servers.","Next, you will be asked for the credentials for the first server"])
    server1 = ConnectionSpec.uf_create(stdscr)
    cursesplus.messagebox.showinfo(stdscr,["Now, input for the second server."])
    server2 = ConnectionSpec.uf_create(stdscr)
    outputoption = cursesplus.coloured_option_menu(stdscr,["On-Screen","Save Excel File","Both"],"How would you like to view the results?")
    writefile = outputoption > 0
    showonscreen = outputoption == 0 or outputoption == 2
    if writefile:
        outdir = cursesplus.filedialog.openfolderdialog(stdscr,"Choose an output directory for the report file.")
        outfile = cursesplus.cursesinput(stdscr,"Write a name for the output file",prefiltext=".xlsx")
        outputpath = outdir + "/" + outfile
    #Tests: 1 (Does the column exist?) 2 (Is the column in the right order?), 3 (Does column exist (reverse))
    #Prog - (Querrying from server 1), 
    prog = cursesplus.ProgressBar(stdscr,3,cursesplus.ProgressBarTypes.FullScreenProgressBar,cursesplus.ProgressBarLocations.TOP,message="Doing stuff",show_log=True)
    prog.step("Loading from server 1",True)

    data1 = server1.run_query(f"select * from INFORMATION_SCHEMA.COLUMNS where TABLE_CATALOG = '{server1.db}' order by TABLE_SCHEMA, TABLE_NAME, ORDINAL_POSITION ")
    prog.step("Loading from server 2",True)
    data2 = server2.run_query(f"select * from INFORMATION_SCHEMA.COLUMNS where TABLE_CATALOG = '{server2.db}' order by TABLE_SCHEMA, TABLE_NAME, ORDINAL_POSITION ")
    prog.max = 2*max([len(data1),len(data2)])+5
    prog.appendlog(f"Server 1 has a total of {len(data1)} columns.")
    prog.appendlog(f"Server 2 has a total of {len(data2)} columns.")

    #Now time to process
    prog.appendlog("Running test 1")

    missing_columns_2:list[str] = []
    textual_report_1 = ""

    for column in data1:
        #Each row
        coolname = column["TABLE_SCHEMA"]+"."+column["TABLE_NAME"]+"."+column["COLUMN_NAME"]
        #Will be used as an id
        prog.step(coolname)
        namex = find_matching_column(data2,coolname)
        if namex is None:
            textual_report_1 += f"The column {coolname} could not be found on server 2.\n\n"
            missing_columns_2.append(coolname)
        else:
            continue

    textual_report_3 = ""
    mismatched_columns:list[list[dict]] = []
    prog.appendlog("Running test 2")
    for column in data1:
        #Each row again
        coolname = column["TABLE_SCHEMA"]+"."+column["TABLE_NAME"]+"."+column["COLUMN_NAME"]
        #Will be used as an id
        prog.step(coolname)
        if not coolname in missing_columns_2:
            #Don't lookup for missing data
            matcher = find_matching_column(data2,coolname)
            dest_index = matcher["ORDINAL_POSITION"]
            src_index = column["ORDINAL_POSITION"]
            if src_index != dest_index:
                mismatched_columns.append([column,matcher])
                textual_report_3 += f"{coolname} mismatched position: On server 1 it is {src_index}, but on server 2 it is {dest_index}\n\n"
    if writefile:
        prog.step("Saving data")

        missing_column_table = pandas.DataFrame(columns=["Table Schema","Table Name","Column Name"])
        for missingcolumn in missing_columns_2:
            missing_column_table.loc[len(missing_column_table)] = missingcolumn.split(".")

        mismatch_table = pandas.DataFrame(columns=["Table Schema","Table Name","Column Name","Server 1 Ordinal Position","Server 2 Ordinal Position"])
        for mismatch in mismatched_columns:
            mismatch_table.loc[len(mismatch_table)] = [mismatch[0]["TABLE_SCHEMA"],mismatch[0]["TABLE_NAME"],mismatch[0]["COLUMN_NAME"],mismatch[0]["ORDINAL_POSITION"],mismatch[1]["ORDINAL_POSITION"]]

        dfs = {"Missing Columns":missing_column_table,"Mismatched Columns":mismatch_table}

        with pandas.ExcelWriter(outputpath) as writer:
            #missing_column_table.to_excel(writer,sheet_name="Missing Columns",index=False)
            #mismatch_table.to_excel(writer,sheet_name="Mismatched Columns",index=False)
            for sheetname, df in dfs.items():  # loop through `dict` of dataframes
                df.to_excel(writer, sheet_name=sheetname,index=False)  # send df to writer
                worksheet = writer.sheets[sheetname]  # pull worksheet object
                for idx, col in enumerate(df):  # loop through all columns
                    series = df[col]
                    max_len = max((
                        series.astype(str).map(len).max(),  # len of largest item
                        len(str(series.name))  # len of column name/header
                        )) + 1  # adding a little extra space
                    worksheet.set_column(idx, idx, max_len)  # set column width

    cursesplus.messagebox.showinfo(stdscr,["Finished successfully."])

    if showonscreen:
        while True:
            viewoption = cursesplus.coloured_option_menu(stdscr,["Columns not found on server 2","Disordered columns (1 -> 2)","Quit program"],"Data Results")

            if viewoption == 0:
                cursesplus.textview(stdscr,text=textual_report_1)

            elif viewoption == 1:
                cursesplus.textview(stdscr,text=textual_report_3)

            if viewoption == 2:
                return

    
try:
    curses.wrapper(main)
except KeyboardInterrupt:
    pass#Keyboard interrupt errors will confuse the user