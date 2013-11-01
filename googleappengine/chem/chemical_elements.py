'''
Created on 29 Sep 2013

@author: DT
'''
import cgi
from google.appengine.api import users
import webapp2

import csv

MAIN_PAGE_HTML = """\
<html>
  <body>
  This tool is designed to character match the letters in your name to elements in the periodic table. Please enter your name in the text box below:
    <form action="/outresult" method="post">
      <div><input type="text" name="content"></input></div>
      <div><input type="submit" value="Submit"></div>
    </form>
  </body>
</html>
"""


class MainPage(webapp2.RequestHandler):

    def get(self):
        self.response.write(MAIN_PAGE_HTML)

class OutputPage(webapp2.RequestHandler):

    def post(self):
        self.response.write('<html><body>Output:<pre>')
        R = Reader()
        R.name = str(self.request.get('content')).lower()

        ES = ElementString(R.name, R.element_list)
        ES.findAllElementsInName()
        ES.orderElements()
        ES.selectElements()

        for e in ES.element_selection:
            printable = e.print_all()
            self.response.write(cgi.escape(printable))
        self.response.write('<br>D. Tait (C)2013 </pre></body></html>')


class Element():
    def __init__(self):
        self.atomic_number = None
        self.atomic_mass = None
        self.name = None
        self.symbol = None
        self.name_index = None
    def print_all(self):
        stringReturn = None
        if self.atomic_number != None:
            stringReturn = '[' + str(self.symbol) + '] --- Name: ' + str(self.name) + ' Symbol: ' + str(self.symbol) + ' Atomic Number: ' + str(self.atomic_number) + ' Atomic Mass: ' + str(self.atomic_mass) + '\n'
        else:
            stringReturn = str(self.name).upper() + '\n'
        return stringReturn
        
class Reader():
    def __init__(self):
        self.element_list = []
        self.name = None
        self.periodicTableReader()
        
    def periodicTableReader(self):
        f=open('periodic_table.csv','rb')
        reader=csv.reader(f)
    
        for line in reader:
            element = Element() #0: atomic number, 1: atomic mass 2: name, 3: symbol
            element.atomic_number = line[0]
            element.atomic_mass = line[1]
            element.name = line[2]
            element.symbol = line[3]
            self.element_list.append(element)
    
##    def activateInputConsole(self):
##        self.name = raw_input('Write Name: ').lower()


class ElementString():
    def __init__(self, name, element_list):
        self.name = name
        self.element_list = element_list
        
        self.elements_in_name = []
        self.elements_in_order = []
        self.element_selection = []
        
    def findAllElementsInName(self):
        for e_item in self.element_list:
            e_symbol =  e_item.symbol.lower()
            if e_symbol in self.name:
                e_position = self.findElementPosition(e_symbol, self.name)
                e_object = (e_item, e_position)
                self.elements_in_name.append(e_object)
    
    def findElementPosition(self, symbol, name):
        positions_in_name = []
        start_position = name.find(symbol)
        end_position  = start_position+(len(symbol))
        positions_in_name.append(range(start_position, end_position))
        return positions_in_name

    def orderElements(self):
        positions_in_name = [i[1] for i in self.elements_in_name]
        sorted_position_indices = sorted(range(len(positions_in_name)), key=lambda k: positions_in_name[k])
        for pos in sorted_position_indices:
            self.elements_in_order.append(self.elements_in_name[pos][0])
    
    def selectElements(self):
        element_selection = []
        letter_index = 0
        while letter_index < len(self.name):
            possible_elements = []
            for element in self.elements_in_order:
                symbol = element.symbol.lower()
                symbol_length = len(symbol)
                if self.name[letter_index:(letter_index+symbol_length)] == symbol:
                    possible_elements.append(element)
            if len(possible_elements) > 0:
                longest_element = None
                longest_element_size = 0
                for element in possible_elements:
                    if len(element.symbol) > longest_element_size:
                        longest_element = element
                        longest_element_size = len(element.symbol)
                self.element_selection.append(longest_element)
                letter_index += len(longest_element.symbol)
            else:
                e = Element()
                e.name = self.name[letter_index:(letter_index+1)]
                self.element_selection.append(e)
                letter_index += 1
                
        return element_selection

application = webapp2.WSGIApplication([
    ('/', MainPage),
    ('/outresult', OutputPage),
], debug=True)    


        
    
        
        
