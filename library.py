import csv
import sqlite3
from datetime import date
from datetime import timedelta

class Catalog:
#####
## General notes:
##
## The system uses a three-table data model:
## 1) A Look-up table of holdings categories with their descriptive captions.
## 2) A catalog table with all the relevant data (category, title, author, 
##    cutter, label note, times circulated, etc)
##
## 3) A circulation table with all currently checked-out books, the name of 
##    the patron holding them, when they were checked out and when due back.
##        
## A cutter is a label code to identify a given book.  Typically books are 
## cuttered by author's last name. If no author is given for a book, it will 
## typically be cuttered by the book's title.
##
## The label note is a secondary code to identify between multiple copies or 
## volumes of a given book.
##
## As currently coded, I have left the file path for the database and 
## attendant files and logs unspecified; this will be set upon local installation.
##
## For ease of data validation, I have echoed the list of categories from the 
## db.categories table into an object attribute, self.cats
##
#####
	def __init__(self):
		self.db=sqlite3.connect('$Path/library.db')
		self.cursor = self.db.cursor()
		self.checkDB()
		self.log = open('$Path/transactions.log','a+')
		self.cats=self.getCats(self)
		
	def checkDB(self):
		self.cursor.execute('''create table if not exists categories (
                                    category text primary key,
                                    definition text)''')
		self.cursor.execute('''create table if not exists catalog (
                                    uid integer,
                                    category text, 
                                    accession integer,
                                    title text collate nocase not blank,
                                    author text collate nocase,
                                    cutter text collate nocase not blank,
                                    note text collate nocase,
                                    times_circulated integer default 0,
                                    date aded date,
                            		primary key (uid),
		                           foreign key (category) 
                                      references categories(category)''')
		self.cursor.execute('''create index if not exists authors on catalog(author)''')
		self.cursor.execute('''create index if not exists titles on catalog(title)''')
		self.cursor.execute('''create table if not exists circulation (
                                    category text,
		                           accession integer, 
                             		WhoChecked text collate nocase not blank,
		                           dateOut date, 
                                    dateDue date
                            		foreign key(category) references catalog(category)
		                           foreign key(accession) references catalog(accession))''')
		self.db.commit()

	def getCats(self):
		results=self.cursor.execute('select category from catalog').fetchall()
		return [x[0] for x in results]
		
	def addBook(self,cat,title,author):
		accession=1+self.cursor.execute('select count(category)\n'
                                         'from catalog where category=?',cat)
		record=(cat,accession,title,author)
		self.cursor.execute('insert into catalog values(?,?,?,?)', record)
		self.db.commit()
		
	def delBook(self,cat,accessionNo):
		self.cursor.execute('delete from catalog\n'
                             'where category=cat\n'
                             '  and accession=acessionNo')
		self.db.commit()
		
	def shelfList(self,catCodes, fromDate=date(1980,1,1), toDate=date(9999,12,12)):
		self.cursor.execute('create table fromCats (category text)')
		dates=(fromDate, toDate)
		for code in catCodes:
			self.cursor.execute('insert into fromCats values (?)',code)
		self.cursor.execute('select category, accession, title,\n'
                             '       author, cutter\n'
                             'from catalog t1\n'
                             'join fromCats t2\n'
                             '  on t1.category = t2.category\n'
                             '  and t1.dateAdded between (?) and (?)', dates)
		hits=self.cursor.fetchall()
		
		listFile = open('$Path/shelf_list.txt', 'w')
		for hit in hits:  
			listFile.write("\t".join(str(x) for x in hit)+"\n")
		listFile.close()
		
	def findBook(self,cat="%",ti="%",au="%"):
		query=(cat,ti,au)
		self.cursor.execute('select category, title, author, cutter, note\n'
                             'from catalog\n'
                             'where category=?\n'
                             '  and title like ?\n'
                             '  and author like ?', query)
		hits=self.cursor.fetchall()
		return hits
		
	def checkIn(self,cat,ti,au):
		entry=(cat,ti,au)
		self.cursor.execute('delete from circulation\n'
                             'where category=?\n'
                             '  and title=?\n'
                             '  and author=?',entry)
		self.db.commit()
		
	def checkOut(self,category,accession,patronName):
		out=date.today()
		due=out+timedelta(days=14)
		entry=(category,accession,patronName,out,due)
		self.cursor.execute('select title, note\n'
                             'from catalog\n'
                             'where category=?\n'
                             '  and accession=?',(category, accession))
		entry+=self.cursor.fetchone()
		self.cursor.execute('update catalog\n'
                             'set timesCirculated = timesCirculated + 1\n'
                             'where category=?\n'
                             '  and accession=?',entry[:2])
		self.cursor.execute('insert into circulation values (?,?,?,?,?)',entry[:-2])
		self.db.commit()
		self.log.write('{2} checked out {5} ({6}) on {3}, due back {4}\n'.format(entry))
		
	def addCat(self,cat):
		self.cursor.execute('insert into categories values(?)',(cat,))
		self.db.commit()
		self.cats=self.getCats()
	
	def delCat(self,cat):
		self.cursor.execute('delete from categories where category=?',(cat,))
		self.db.commit()
		self.cats=self.getCats()
		
	def outList(self):
		outFile=open("$path/currently_out.txt",'w')
		checkedOut=self.cursor.execute('''select t2.WhoChecked, t1.title, t1.author, t1.cutter, t1.note, t2.dateDue 
		from catalog t1, circulation t2 
		where t1.category=t2.category
		and t1.accession=t2.accession''').fetchall()
		outFile.write("\t".join("Person's Name","Title","Author","Cutter","Label Note","Date Due"))
		for book in checkedOut:
			outFile.write("\t".join(map(str,book))+"\n")
		outFile.close()
		
	def dueList(self):
		outFile=open("$path/overdue.txt",'w')
		nowDue=self.cursor.execute('''select t1.title, t1.author, t1.cutter, t1.note, t2.WhoChecked, t2.dateDue 
		from catalog t1, circulation t2 
		where t2.dateDue >= ?
		and t1.category=t2.category
		and t1.accession=t2.accession''',date.today()).fetchall()
		outFile.write("\t".join("Person's Name","Title","Author","Cutter","Label Note","Date Due"))
		for book in nowDue:
			outFile.write("\t".join(map(str,book))+"\n")
		outFile.close()