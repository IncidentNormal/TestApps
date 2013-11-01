'''
Created on 29 Sep 2013

@author: DT
'''
import cgi
from google.appengine.api import users
import webapp2

import pickle


class Resolution():
    LOW = (560,315)
    MED = (640,360)
    HIGH = (853,480)


class MainPage(webapp2.RequestHandler):

    def get(self):
        filename = 'ted_db.pk1'
        res = Resolution.HIGH

        PKL = PickleReader()
        PKL.readPickleFile(filename)
        PKL.createHTML()
        self.response.write(PKL.html)

#class OutputPage(webapp2.RequestHandler):
#
#    def post(self):
#        self.response.write('<html><body>Output:<pre>')
#        R = Reader()
#        R.name = str(self.request.get('content')).lower()
#
#        ES = ElementString(R.name, R.element_list)
#        ES.findAllElementsInName()
#        ES.orderElements()
#        ES.selectElements()
#
#        for e in ES.element_selection:
#            printable = e.print_all()
#            self.response.write(cgi.escape(printable))
#        self.response.write('<br>D. Tait (C)2013 </pre></body></html>')

class PickleReader():
    def __init__(self):
        self.rfid = None
        self.ted_database = []
        self.MAIN_PAGE_HTML = ''
    def readPickleFile(self, filename):
        self.rfid = open(filename, 'rb')
        self.ted_database = pickle.load(self.rfid)
        self.rfid.close()
    def printDatabase(self):
        self.ted_database.sort(key=lambda TedTalk: float(TedTalk.id))
        for ted in self.ted_database:
            print ted.id, ted.name
    def createHTML(self):
        html = '''<html>
                  <body>
                  <ul>'''
        for ted in self.ted_database:
                html += '<a href="' + ted.url2 + '" target="_blank">' + ted.name + '</a>' + '\n'
        
        html += '''</ul>
                   </body>
                   </html>'''
        self.html = html

#application = webapp2.WSGIApplication([
#    ('/', MainPage),
#    ('/outresult', OutputPage),
#], debug=True)    

application = webapp2.WSGIApplication([
    ('/', MainPage),
], debug=True)   
