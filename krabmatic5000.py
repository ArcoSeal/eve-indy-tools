#!/usr/bin/env python

import sys
import os
import platform
import ctypes
import webbrowser
from PyQt5.QtCore import *
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *

import krabtools

class OutLog:
    def __init__(self, editBox, out=None):
        """(editBox, out=None, color=None) -> can write stdout, stderr to a QTextEdit.
        editBox = QTextEdit object
        out = alternate stream ( can be the original sys.stdout )
        """
        self.editBox = editBox
        self.out = out

    def write(self, m):
        self.editBox.moveCursor(QTextCursor.End)
        self.editBox.insertPlainText( m )

        if self.out: self.out.write(m)

    def flush(self):
        pass

class ConsoleOutput(QWidget):
    def __init__(self, parent):
        global oldstdout

        super(ConsoleOutput, self).__init__(parent)

        # self.resize(250,250)

        self.consoleOutputBox = QTextEdit()
        self.consoleOutputBox.setReadOnly(True)

        mainLayout = QGridLayout()
        mainLayout.addWidget(self.consoleOutputBox,0,0)

        self.setLayout(mainLayout)

        oldstdout = sys.stdout # keep link to original stdout (normally the terminal)
        sys.stdout = OutLog(self.consoleOutputBox, oldstdout) # redirect stdout to OutLog, which will write to consoleOutputBox and also the original stdout

class TableWidgetWCopyPaste(QTableWidget):
    # adapted from http://www.voidynullness.net/blog/2013/06/21/qt-qtablewidget-copy-paste-row-into-excel/
    def __init__(self, parent=None):
        super(TableWidgetWCopyPaste, self).__init__(parent)

    def keyPressEvent(self, event):
        if event.matches(QKeySequence.Copy):
            self.copy()
        else:
            QTableWidget.keyPressEvent(self, event)

    def copy(self):
        self.selection = self.selectionModel()
        self.indexes = self.selection.selectedIndexes()
        if len(self.indexes) < 1:
            # Nothing selected
            return
        
        self.previousrow = None
        for idx in self.indexes:
            self.thisrow = idx.row()
            self.thisitem = self.item(self.thisrow, idx.column())
            if self.thisitem:
                self.thisitem = self.thisitem.text()
            else:
                self.thisitem = '' # for entries which can't be parsed as text
            
            if not self.previousrow: # first item in selection (previourow == None)
                self.copytext = self.thisitem
            else:
                if self.previousrow != self.thisrow:
                    self.copytext += '\n' # new row
                else:
                    self.copytext += '\t' # new column
                
                self.copytext += self.thisitem

            self.previousrow = self.thisrow

        QApplication.clipboard().setText(self.copytext)

    def findColByHeaderText(self,header):
        self.found = None
        for self.cc in range(0,self.columnCount()):
            if self.horizontalHeaderItem(self.cc).text() == header: self.found = self.cc

        return self.found

    def appendCol(self, header=None):
        self.cc = self.columnCount()-1+1 # last column index = no of cols - 1
        self.insertColumn(self.cc)
        if header: self.setHorizontalHeaderItem(self.cc, QTableWidgetItem(header))
        return self.cc

class IndyAppMain(QMainWindow):
    def __init__(self):
        super().__init__()

        global masterPriceList
        
        masterPriceList = {}

        self.initUI()
        loadMasterPriceList()

    def initUI(self):
        self.setWindowTitle('KrabMatic 5000')
        self.setWindowIcon(QIcon('./icons/fat-cat-icon_256.png'))

        self.statusBar()

        self.initMenuBar()

        self.mainInterface = mainInterfaceWidget(self)
        self.setCentralWidget(self.mainInterface)

        self.resize(500,500)

        self.statusBar().showMessage('Ready')

        self.show()

    def initMenuBar(self):

        # File menu stuff

        loadPriceAction = QAction('&Load', self)        
        loadPriceAction.setShortcut('Ctrl+L')
        loadPriceAction.setStatusTip('Load market prices from local DB')
        loadPriceAction.triggered.connect(loadMasterPriceList)

        savePriceAction = QAction('&Save', self)        
        savePriceAction.setShortcut('Ctrl+S')
        savePriceAction.setStatusTip('Save market prices to local DB')
        savePriceAction.triggered.connect(saveMasterPriceList)

        deletePriceDBAction = QAction('Delete price DB', self)        
        deletePriceDBAction.setStatusTip('Delete local price DB')
        deletePriceDBAction.triggered.connect(deleteMasterPriceListDB)

        exitAction = QAction('&Exit', self)        
        exitAction.setShortcut('Ctrl+Q')
        exitAction.setStatusTip('Exit application')
        exitAction.triggered.connect(self.close)

        # Help menu stuff

        aboutAction = QAction('&About', self)        
        aboutAction.setStatusTip('About')
        aboutAction.triggered.connect(self.openAbout)

        docsAction = QAction('&Documentation', self)        
        docsAction.setShortcut('F1')
        docsAction.setStatusTip('Consult extensive documentation')
        docsAction.triggered.connect(self.openDocs)

        # set up menus

        menubar = self.menuBar()
        menubar.setNativeMenuBar(False)
        
        fileMenu = menubar.addMenu('&File')
        fileMenu.addAction(loadPriceAction)
        fileMenu.addAction(savePriceAction)
        fileMenu.addAction(deletePriceDBAction)
        fileMenu.addAction(exitAction)
        
        helpMenu = menubar.addMenu('&Help')
        helpMenu.addAction(docsAction)
        helpMenu.addAction(aboutAction)

    def openAbout(self):
        webbrowser.open('http://nog8s.space')

    def openDocs(self):
        QMessageBox.information(self, 'Documentation', 'there aren''t any lol')

    def setBusyMode(self, setBusy):
        global appIsBusy

        if 'appIsBusy' not in globals(): appIsBusy = False

        if setBusy and not appIsBusy:
            appIsBusy = True

            self.statusBar().clearMessage()
            self.workingMessage = QLabel('Working...')
            self.statusBar().addWidget(self.workingMessage)
            
            QApplication.setOverrideCursor(QCursor(Qt.WaitCursor))
        
        elif not setBusy and appIsBusy:
            self.statusBar().removeWidget(self.workingMessage)
            self.statusBar().showMessage('Done')
            QApplication.restoreOverrideCursor()
            appIsBusy = False

    def closeEvent(self, event):
        if masterPriceList_hasBeenUpdated: saveMasterPriceList()
        event.accept()

class mainInterfaceWidget(QWidget):
    def __init__(self, parent):
        super().__init__()

        self.initUI()      
        
    def initUI(self):
        # build panel
        self.buildPanel = QGroupBox('Builds')

        self.newBuildBtn = QPushButton('New Build')
        self.newBuildBtn.clicked.connect(self.createNewBuild)

        self.loadBuildBtn = QPushButton('Load Build')

        self.buildPanelLayout = QGridLayout()
        self.buildPanelLayout.addWidget(self.newBuildBtn,0,0)
        self.buildPanelLayout.addWidget(self.loadBuildBtn,0,1)

        self.buildPanel.setLayout(self.buildPanelLayout)

        # Aux data panel
        self.auxDataPanel = QGroupBox('Auxiliary data (SDE)')

        self.checkAuxDataBtn = QPushButton('Check Aux Data')
        self.checkAuxDataBtn.clicked.connect(self.checkAuxData)
        self.forceUpdateAuxDataCBx = QCheckBox('Force update')

        self.auxDataPanelLayout = QGridLayout()
        self.auxDataPanelLayout.addWidget(self.checkAuxDataBtn,0,0)
        self.auxDataPanelLayout.addWidget(self.forceUpdateAuxDataCBx,0,1)

        self.auxDataPanel.setLayout(self.auxDataPanelLayout)

        # Market price data
        self.marketPricePanel = QGroupBox('Market price data')
        
        self.loadMarketPriceBtn = QPushButton('Load cache')
        self.loadMarketPriceBtn.clicked.connect(loadMasterPriceList)
        
        self.saveMarketPriceBtn = QPushButton('Save cache')
        self.saveMarketPriceBtn.clicked.connect(saveMasterPriceList)
        
        self.refreshMarketPriceBtn = QPushButton('Refresh from CREST')
        self.refreshMarketPriceBtn.clicked.connect(refreshMasterPriceList)
        
        self.clearMarketPriceBtn = QPushButton('Clear cache')
        self.clearMarketPriceBtn.clicked.connect(clearMasterPriceList)
        
        self.deleteMarketPriceDBBtn = QPushButton('Delete local DB')
        self.deleteMarketPriceDBBtn.clicked.connect(deleteMasterPriceListDB)

        self.marketPricePanelLayout = QGridLayout()
        self.marketPricePanelLayout.addWidget(self.loadMarketPriceBtn,0,0,1,3)
        self.marketPricePanelLayout.addWidget(self.saveMarketPriceBtn,0,3,1,3)
        self.marketPricePanelLayout.addWidget(self.refreshMarketPriceBtn,1,0,1,2)
        self.marketPricePanelLayout.addWidget(self.clearMarketPriceBtn,1,2,1,2)
        self.marketPricePanelLayout.addWidget(self.deleteMarketPriceDBBtn,1,4,1,2)

        self.marketPricePanel.setLayout(self.marketPricePanelLayout)

        # Console output
        self.consoleOutputPanel = QGroupBox('Console output')

        self.consoleOutputBox = ConsoleOutput(self)

        self.consoleOutputPanelLayout = QGridLayout()
        self.consoleOutputPanelLayout.addWidget(self.consoleOutputBox,0,0)

        self.consoleOutputPanel.setLayout(self.consoleOutputPanelLayout)

        # assemble main layout
        self.mainLayout = QVBoxLayout()
        self.mainLayout.addWidget(self.buildPanel)
        self.mainLayout.addWidget(self.auxDataPanel)
        self.mainLayout.addWidget(self.marketPricePanel)
        self.mainLayout.addWidget(self.consoleOutputPanel)

        self.setLayout(self.mainLayout)

    def createNewBuild(self):
        self.newBuildWindow = buildWidget()
        self.newBuildWindow.show()

    def checkAuxData(self):
        global masterPriceList

        self.parent().setBusyMode(True)
        print('Initialising auxiliary data:')
                
        if self.forceUpdateAuxDataCBx.isChecked():
            print('Forcing update:')
            krabtools.forceupdateauxdata = True

        krabtools.initauxdata()
        loadBPProducts()
        deleteAllIcons()
        masterPriceList = {}
        print('Initialisation complete.')
        
        self.forceUpdateAuxDataCBx.setChecked(False)

        self.parent().setBusyMode(False)

class buildWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__()

        if 'allBPProducts' not in globals(): loadBPProducts()

        self.baseMatsTableHeaders = {
                                    'name'              :   'Name',
                                    'qty'               :   'Quantity',
                                    'unitbuy'           :   'Unit Price (buy)',
                                    'unitsell'          :   'Unit Price (sell)',
                                    'margindelta'       :   'Profit Delta',
                                    }

        self.matsTableHeaders = {
                                    'name'              :   'Name',
                                    'qty'               :   'Quantity',
                                    'buildfeetotal'    :   'Build Fee (total)',
                                    }

        self.setWindowTitle('New build')
        self.setWindowIcon(QIcon('./icons/fat-cat-icon_256.png'))

        self.inventmode = False # for first init of interface
        self.firstInit = True

        self.initUI()

        self.productSelectBox.setText('Svipul') # default value

    def initUI(self):

        self.initProductSelectPanel()
        self.initInventPanel()
        self.initMEPanel()
        self.initTEPanel()
        self.initRunsPanel()
        self.initButansPanel()
        self.assembleBuildPanel()

        self.firstInit = False

    def initProductSelectPanel(self):
        # What are we building?

        self.productSelectBoxLabel = QLabel('Product to build:')

        self.productSelectBoxModel = QStringListModel()
        self.productSelectBoxModel.setStringList(allBPProducts)

        self.productSelectBoxCompleter = QCompleter()
        self.productSelectBoxCompleter.setModel(self.productSelectBoxModel)
        self.productSelectBoxCompleter.setCaseSensitivity(False)

        self.productSelectBox = QLineEdit()
        self.productSelectBox.setCompleter(self.productSelectBoxCompleter)
        self.productSelectBox.textChanged.connect(self.updatedProduct) # turn invention on/off if necessary
        # self.productSelectBox.returnPressed.connect(self.getMats)

        self.productSelectPanel = QHBoxLayout()
        self.productSelectPanel.addWidget(self.productSelectBoxLabel)
        self.productSelectPanel.addWidget(self.productSelectBox)

    def initInventPanel(self):
        self.inventPanel = QGroupBox('Invention')

        # Invention
        self.inventFromLabel = QLabel('Invent from:')

        self.inventFromCB = QComboBox()
        self.inventFromCB.currentTextChanged.connect(self.updateInventStats)

        self.decryptorLabel = QLabel('Decryptor type:')

        self.decryptorTypeCB = QComboBox()
        self.decryptorTypeCB.addItems(sorted(krabtools.presets.decryptors.keys()))
        self.decryptorTypeCB.currentTextChanged.connect(self.updateInventStats)
        
        self.inventChanceLabel = QLabel()

        self.inventCostPerLabel = QLabel('Invent cost per run: ')
        self.inventCostPerBuySellMarginDiffLabel = QLabel('Buy/Sell margin delta: ')

        # off at first init
        self.inventFromCB.setEnabled(False)
        self.decryptorTypeCB.setEnabled(False)

        self.inventPanelLayout = QGridLayout()
        self.inventPanelLayout.addWidget(self.inventFromLabel,0,0)
        self.inventPanelLayout.addWidget(self.inventFromCB,0,1)
        self.inventPanelLayout.addWidget(self.decryptorLabel,0,2)
        self.inventPanelLayout.addWidget(self.decryptorTypeCB,0,3)
        self.inventPanelLayout.addWidget(self.inventChanceLabel,0,4)
        self.inventPanelLayout.addWidget(self.inventCostPerLabel,1,0,1,3)
        self.inventPanelLayout.addWidget(self.inventCostPerBuySellMarginDiffLabel,1,3,1,2)

        self.inventPanel.setLayout(self.inventPanelLayout)

    def initMEPanel(self):
        self.MEPanel = QGroupBox('ME')

        ## Product ME savings
        # Product ME savings (BP)        
        self.BPMELabel = QLabel('Blueprint ME:')
        
        self.BPMELabel2 = QLabel('%')

        self.BPMEBox = QSpinBox()
        self.BPMEBox.setMinimum(0)
        self.BPMEBox.setMaximum(10)

        # needs changed + set back at first init
        self.BPMEBox.setValue(1)
        self.BPMEBox.setValue(0)

        self.BPMELayout = QHBoxLayout()
        self.BPMELayout.addWidget(self.BPMELabel)
        self.BPMELayout.addWidget(self.BPMEBox)
        self.BPMELayout.addWidget(self.BPMELabel2)

        # Product ME savings (POS)
        self.otherMELabel = QLabel('Other savings (%):')
        self.otherMELabel.setToolTip('Additional material efficiency savings, entered as comma separated list e.g. 2,5 for 2% POS saving & 5% skill saving')
        self.otherMEBox = QLineEdit()

        self.otherMELayout = QHBoxLayout()
        self.otherMELayout.addWidget(self.otherMELabel)
        self.otherMELayout.addWidget(self.otherMEBox)

        ## Component ME savings
        # Component ME savings (BP)
        self.compBPMELabel = QLabel('Components ME:')
        
        self.compBPMELabel2 = QLabel('%')

        self.compBPMEBox = QSpinBox()
        self.compBPMEBox.setMinimum(0)
        self.compBPMEBox.setMaximum(10)

        # needs changed + set back at first init
        self.compBPMEBox.setValue(1)
        self.compBPMEBox.setValue(0)

        self.compBPMELayout = QHBoxLayout()
        self.compBPMELayout.addWidget(self.compBPMELabel)
        self.compBPMELayout.addWidget(self.compBPMEBox)
        self.compBPMELayout.addWidget(self.compBPMELabel2)

        # Component ME savings (POS)
        self.compOtherMELabel = QLabel('Other savings (%):')
        self.compOtherMELabel.setToolTip('Additional material efficiency savings, entered as comma separated list e.g. 2,5 for 2% POS saving & 5% skill saving')
        self.compOtherMEBox = QLineEdit()

        self.compOtherMELayout = QHBoxLayout()
        self.compOtherMELayout.addWidget(self.compOtherMELabel)
        self.compOtherMELayout.addWidget(self.compOtherMEBox)

        self.MEPanelLayout = QGridLayout()
        self.MEPanelLayout.addLayout(self.BPMELayout,0,0, alignment=Qt.AlignRight)
        self.MEPanelLayout.addLayout(self.otherMELayout,0,1)
        self.MEPanelLayout.addLayout(self.compBPMELayout,1,0, alignment=Qt.AlignRight)
        self.MEPanelLayout.addLayout(self.compOtherMELayout,1,1)

        self.MEPanel.setLayout(self.MEPanelLayout)

    def initTEPanel(self):
        self.TEPanel = QGroupBox('TE')

        ## Product TE savings
        # Product TE savings (BP)        
        self.BPTELabel = QLabel('Blueprint TE:')
        
        self.BPTELabel2 = QLabel('*2 %')

        self.BPTEBox = QSpinBox()
        self.BPTEBox.setMinimum(0)
        self.BPTEBox.setMaximum(10)

        # needs changed + set back at first init
        self.BPTEBox.setValue(1)
        self.BPTEBox.setValue(0)

        self.BPTELayout = QHBoxLayout()
        self.BPTELayout.addWidget(self.BPTELabel)
        self.BPTELayout.addWidget(self.BPTEBox)
        self.BPTELayout.addWidget(self.BPTELabel2)

        # Product TE savings (POS)
        self.otherTELabel = QLabel('Other savings (%):')
        self.otherTELabel.setToolTip('Additional time efficiency savings, entered as comma separated list e.g. 2,5 for 2% POS saving & 5% skill saving')
        self.otherTEBox = QLineEdit()

        self.otherTELayout = QHBoxLayout()
        self.otherTELayout.addWidget(self.otherTELabel)
        self.otherTELayout.addWidget(self.otherTEBox)

        ## Component TE savings
        # Component TE savings (BP)
        self.compBPTELabel = QLabel('Components TE:')
        
        self.compBPTELabel2 = QLabel('*2 %')

        self.compBPTEBox = QSpinBox()
        self.compBPTEBox.setMinimum(0)
        self.compBPTEBox.setMaximum(10)

        # needs changed + set back at first init
        self.compBPTEBox.setValue(1)
        self.compBPTEBox.setValue(0)

        self.compBPTELayout = QHBoxLayout()
        self.compBPTELayout.addWidget(self.compBPTELabel)
        self.compBPTELayout.addWidget(self.compBPTEBox)
        self.compBPTELayout.addWidget(self.compBPTELabel2)

        # Component TE savings (POS)
        self.compOtherTELabel = QLabel('Other savings (%):')
        self.compOtherTELabel.setToolTip('Additional time efficiency savings, entered as comma separated list e.g. 2,5 for 2% POS saving & 5% skill saving')
        self.compOtherTEBox = QLineEdit()

        self.compOtherTELayout = QHBoxLayout()
        self.compOtherTELayout.addWidget(self.compOtherTELabel)
        self.compOtherTELayout.addWidget(self.compOtherTEBox)

        self.TEPanelLayout = QGridLayout()
        self.TEPanelLayout.addLayout(self.BPTELayout,0,0, alignment=Qt.AlignRight)
        self.TEPanelLayout.addLayout(self.otherTELayout,0,1)
        self.TEPanelLayout.addLayout(self.compBPTELayout,1,0, alignment=Qt.AlignRight)
        self.TEPanelLayout.addLayout(self.compOtherTELayout,1,1)

        self.TEPanel.setLayout(self.TEPanelLayout)

    def initRunsPanel(self):
        # Runs to build, runs per BP

        self.runsPanel = QGroupBox('Runs')

        self.runstobuildLabel = QLabel('# of products to build:')

        self.runsToBuildBox = QSpinBox()
        self.runsToBuildBox.setMinimum(1)
        self.runsToBuildBox.setMaximum(99999)
        self.runsToBuildBox.setValue(1)

        self.runsPerBPLabel = QLabel('Max runs on BP:')

        self.runsPerBPBox = QSpinBox()
        self.runsPerBPBox.setMinimum(1)
        self.runsPerBPBox.setMaximum(99999)

        # default at first init
        self.runsPerBPBox.setValue(self.runsPerBPBox.maximum())

        self.runsPanelLayout = QHBoxLayout()
        self.runsPanelLayout.addWidget(self.runstobuildLabel)
        self.runsPanelLayout.addWidget(self.runsToBuildBox)
        self.runsPanelLayout.addWidget(self.runsPerBPLabel)
        self.runsPanelLayout.addWidget(self.runsPerBPBox)

        self.runsPanel.setLayout(self.runsPanelLayout)

    def initButansPanel(self):

        # Butans

        self.getCostsCBx = QCheckBox('Get costs')

        self.compareMatSellCBx = QCheckBox('Compare buy/sell')

        self.updateAllBtn = QPushButton('UPDATE')
        self.updateAllBtn.clicked.connect(self.updateAll)

        self.buttonsLayout = QGridLayout()
        self.buttonsLayout.addWidget(self.updateAllBtn,0,0,2,2)
        self.buttonsLayout.addWidget(self.getCostsCBx,0,2)
        self.buttonsLayout.addWidget(self.compareMatSellCBx,1,2)

    def assembleBuildPanel(self):
        self.buildSettingsPanel = QGroupBox('Build Settings')

        self.buildSettingsLayout = QVBoxLayout()
        self.buildSettingsLayout.addLayout(self.productSelectPanel)
        self.buildSettingsLayout.addWidget(self.inventPanel)
        self.buildSettingsLayout.addWidget(self.MEPanel)
        self.buildSettingsLayout.addWidget(self.TEPanel)
        self.buildSettingsLayout.addWidget(self.runsPanel)
        self.buildSettingsLayout.addLayout(self.buttonsLayout)
        self.buildSettingsLayout.addStretch()

        self.buildSettingsPanel.setLayout(self.buildSettingsLayout)

        self.costsPanel = QGroupBox('Costs')
        self.costsTable = QWidget() # starts life as an empty widget
        self.costsPanelLayout = QVBoxLayout()
        self.costsPanelLayout.addWidget(self.costsTable)

        self.costsPanel.setLayout(self.costsPanelLayout)

        self.matsPanel = QGroupBox('Materials')
        self.matsWidget = QWidget() # starts life as an empty widget
        self.matsPanelLayout = QVBoxLayout()
        self.matsPanelLayout.addWidget(self.matsWidget)

        self.matsPanel.setLayout(self.matsPanelLayout)

        self.windowLayout = QGridLayout()
        self.windowLayout.addWidget(self.buildSettingsPanel,0,0)
        self.windowLayout.addWidget(self.costsPanel,1,0)
        self.windowLayout.addWidget(self.matsPanel,0,1,2,1)

        self.setLayout(self.windowLayout)

    def updatedProduct(self):
        if self.productSelectBox.text() in allBPProducts: # only bother if valid product
            if not self.firstInit:
                self.costsPanelLayout.removeWidget(self.costsTable)
                self.costsTable.setParent(None)
                self.costsTable = QWidget()

                self.windowLayout.removeWidget(self.matsWidget)
                self.matsWidget.setParent(None)
                self.matsWidget = QWidget()

            self.productName = self.productSelectBox.text()
            self.productID = krabtools.auxdatatools.getitemid(self.productName)
            
            # reset MEs etc.
            self.runsToBuildBox.setValue(1)
            # self.otherMEBox.setText('')
            # self.otherTEBox.setText('')
            # self.compBPMEBox.setValue(0)
            # self.compBPTEBox.setValue(0)
            # self.compOtherMEBox.setText('')
            # self.compOtherTEBox.setText('')

            self.updateInventMode()

    def updateInventMode(self):
        if self.productSelectBox.text() in allBPProducts: # don't bother if it's not a valid product name

            # blank these labels
            self.inventCostPerLabel.setText('Invent cost per run: ')
            self.inventCostPerBuySellMarginDiffLabel.setText('Buy/Sell margin delta: ')

            if krabtools.auxdatatools.isT2(self.productSelectBox.text()):
                self.switchInventModeOn()
            else:
                self.switchInventModeOff()

    def switchInventModeOn(self):

        self.inventmode = True

        self.updateInventFromCB()

        self.BPMEBox.setEnabled(False)
        self.BPTEBox.setEnabled(False)
        
        self.runsPerBPBox.setEnabled(False)

        self.inventFromCB.setEnabled(True)
        self.decryptorTypeCB.setEnabled(True)

        self.updateInventStats()

    def switchInventModeOff(self):

        self.inventmode = False

        self.inventFromCB.setEnabled(False)
        self.decryptorTypeCB.setEnabled(False)

        self.BPMEBox.setEnabled(True)
        self.BPTEBox.setEnabled(True)

        self.BPMEBox.setValue(0)
        self.BPTEBox.setValue(0)
           
        self.runsPerBPBox.setEnabled(True)
        self.runsPerBPBox.setValue(self.runsPerBPBox.maximum())

        self.inventcostperbp, self.inventcostperrun = None, None

        self.updateInventFromCB()

    def updateInventFromCB(self):
        self.inventFromCB.currentTextChanged.disconnect(self.updateInventStats)

        while self.inventFromCB.count() > 0: self.inventFromCB.removeItem(0)

        if self.inventmode:
            self.inventbase = krabtools.auxdatatools.getinventbase(self.productName)
            if isinstance(self.inventbase, int): self.inventbase = [self.inventbase]
            self.inventFromCB.addItems(sorted(krabtools.auxdatatools.getitemNames(self.inventbase)))

        self.inventFromCB.currentTextChanged.connect(self.updateInventStats)

    def updateInventStats(self):
        self.inventtype = self.inventFromCB.currentText()
        self.decryptortype = self.decryptorTypeCB.currentText()
        
        self.inventChance, self.runsperBP, self.bpME, self.bpTE = krabtools.indytools.calcinventstats(self.inventtype, 4, 4, 4, self.decryptortype)
        
        self.inventChanceLabel.setText(str(round(self.inventChance * 100,1)) + ' %')
        self.BPMEBox.setValue(self.bpME)
        self.BPTEBox.setValue(self.bpTE)
        self.runsPerBPBox.setValue(self.runsperBP)

    def updateMEStats(self):
        self.bpME = self.BPMEBox.value()
        self.otherME = efficiencylist(self.otherMEBox.text())
        self.compBPME = {'ALL' : self.compBPMEBox.value()}

        efflist = efficiencylist(self.compOtherMEBox.text())
        self.compOtherME = {'ALL' : efflist} if efflist else {} # !TODO: individual MEs if bothered

    def updateTEStats(self):
        self.bpTE = self.BPTEBox.value()
        self.otherTE = efficiencylist(self.otherTEBox.text())
        self.compBPTE = {'ALL' : self.compBPTEBox.value()}

        efflist = efficiencylist(self.compOtherTEBox.text())
        self.compOtherTE = {'ALL' : efflist} if efflist else {} # !TODO: individual TEs if bothered

    def updateRunStats(self):
        self.runstobuild = self.runsToBuildBox.value()
        self.runsperBP = self.runsPerBPBox.value()

    def calcInventCost(self):
        global masterPriceList
        self.inventMatsPerBP = krabtools.indytools.getinventmats(self.inventtype, decryptortype=self.decryptortype)

        QApplication.setOverrideCursor(QCursor(Qt.WaitCursor))
        updateMasterPriceList(self.inventMatsPerBP, 'buy', 'Jita')
        QApplication.restoreOverrideCursor()

        self.inventcostperbp = krabtools.indytools.get_matslist_cost_from_pricelist(self.inventMatsPerBP, masterPriceList, order_type='buy', return_type='total')
        self.inventcostperrun = round(self.inventcostperbp * (1 / self.inventChance) * (1 / self.runsperBP), 2)
        self.inventCostPerLabel.setText('Invent cost per run: %s' % floatascurrency(self.inventcostperrun))

    def updateAll(self):
        if self.inventmode:
            self.updateInventStats()
            self.calcInventCost()

        self.updateMEStats()
        self.updateTEStats()
        self.updateRunStats()

        self.getMats()

        if self.getCostsCBx.isChecked():
            self.getCosts()
            if self.compareMatSellCBx.isChecked(): self.compareMatSellPrices()

    def getMats(self):
      
        QApplication.setOverrideCursor(QCursor(Qt.WaitCursor))

        self.runstobuild = self.runsToBuildBox.value()

        if not checkProduct(self.productName): # don't try if not a valid item
            return

        else:
            self.matsList = krabtools.indytools.getmatsforitem(self.productName, n_produced=self.runstobuild, ME=self.bpME, production_efficiences=self.otherME, bpMaxRuns=self.runsperBP)

            self.baseMatsList = krabtools.indytools.getbasematsforitem(self.productName, n_produced=self.runstobuild, ME=self.bpME, production_efficiences=self.otherME, bpMaxRuns=self.runsperBP, ME_components=self.compBPME, production_efficiences_components=self.compOtherME)

            self.matsListNamed, self.baseMatsListNamed = krabtools.indytools.convmatslisttonames(self.matsList), krabtools.indytools.convmatslisttonames(self.baseMatsList)           

            # kill old mats table widget
            self.windowLayout.removeWidget(self.matsWidget)
            self.matsWidget.setParent(None)

            self.matsTableWidget = generateMatsTable(self.matsListNamed, headers=(self.matsTableHeaders['name'], self.matsTableHeaders['qty']), showIcons=[ii for ii in self.matsList])
            self.baseMatsTableWidget = generateMatsTable(self.baseMatsListNamed, headers=(self.baseMatsTableHeaders['name'], self.baseMatsTableHeaders['qty']), showIcons=[ii for ii in self.baseMatsList])

            self.matsWidget = QTabWidget()
            self.matsWidget.addTab(self.matsTableWidget, 'Components')
            self.matsWidget.addTab(self.baseMatsTableWidget, 'Base Materials')

            self.windowLayout.addWidget(self.matsWidget,0,1,2,1)

            if self.width() < self.matsWidget.width():
                self.resize(self.width() + self.matsWidget.width(), self.height())

            if self.height() < self.matsWidget.height():
                self.resize(self.width(), self.height() + self.matsWidget.height())

        QApplication.restoreOverrideCursor()

    def getCosts(self):
        global masterPriceList
        
        QApplication.setOverrideCursor(QCursor(Qt.WaitCursor))

        # kill old costs table widget
        self.costsPanelLayout.removeWidget(self.costsTable)
        self.costsTable.setParent(None)

        # invent cost if necessary
        if self.inventmode: self.calcInventCost()

        # pull market prices as necessary
        updateMasterPriceList(self.baseMatsList, 'buy', 'Jita')
        updateMasterPriceList(self.productName, 'sell', 'Jita')

        # work out costs
        self.buildCosts = krabtools.indytools.calcbuildcosts(self.productID, self.runstobuild, bpMaxRuns=self.runsperBP, baseMatsList=self.baseMatsList, componentsList=self.matsList, baseMatsPriceList=masterPriceList)

        # work out profits
        self.productSellPrice = masterPriceList[self.productID]['sell']
        self.totalCostPerBuild = self.buildCosts['totalCost']
        if self.inventmode:
            self.inventCostPerBuild = self.inventcostperrun * self.runstobuild
            self.totalCostPerBuild += self.inventCostPerBuild
        else:
            self.inventCostPerBuild = None
        self.productRevenue = self.runstobuild * self.productSellPrice
        self.productSellFees = krabtools.evemarket.calcsellfee(self.productRevenue, sell_to_order_type='sell', skillBrokerRelations=1, skillAccounting=2)
        self.profitAbs = self.productRevenue - self.productSellFees - self.totalCostPerBuild
        self.profitMargin = self.profitAbs / self.totalCostPerBuild

        # setup costs table
        self.costsList = []
        if self.inventCostPerBuild: self.costsList.append( ('Invention cost:', self.inventCostPerBuild) )
        self.costsList.append( ('Base materials:', sum(self.buildCosts['baseMatsCosts'].values()) ) )
        self.costsList.append( ('Buy fees:', sum(self.buildCosts['baseMatsBuyFees'].values()) ) )
        self.costsList.append( ('Build fees (components):', sum(self.buildCosts['componentsBuildFees'].values()) ) )
        self.costsList.append( ('Build fees (products):', self.buildCosts['productBuildFee']) )
        self.costsList.append( ('Total cost:', self.totalCostPerBuild) )
        self.costsList.append( ('Total revenue:', self.productRevenue) )
        self.costsList.append( ('Sell fees:', self.productSellFees ) )
        self.costsList.append( ('Profit:', self.profitAbs) )
        self.costsList.append( ('Margin:', str(round(self.profitMargin*100,1))+' %' ))
        self.costsList.append( ('Profit/hr/slot:', floatascurrency(self.profitAbs / (krabtools.indytools.calcjobtime(self.productID, 'Manufacturing', self.runstobuild, TE=self.bpTE, production_time_efficiencies=self.otherTE) / 3600)) ))

        self.costsList = [(ii[0], (floatascurrency(ii[1]) if isinstance(ii[1], float) else ii[1])) for ii in self.costsList] # format costs as currency strings
        self.costsTable = generateMatsTable(self.costsList, headers=('Cost', 'Quantity'), sort_enable=False)
        self.costsPanelLayout.addWidget(self.costsTable)

        # add price data to base mats table
        temp_namecol, temp_unitbuypricecol = self.baseMatsTableWidget.findColByHeaderText(self.baseMatsTableHeaders['name']), self.baseMatsTableWidget.findColByHeaderText(self.baseMatsTableHeaders['unitbuy'])

        if not temp_unitbuypricecol: temp_unitbuypricecol = self.baseMatsTableWidget.appendCol(self.baseMatsTableHeaders['unitbuy'])

        for rr in range(0, self.baseMatsTableWidget.rowCount()):
            temp_thisitemid = krabtools.auxdatatools.getitemid(self.baseMatsTableWidget.item(rr,temp_namecol).text())
            temp_thisbuyprice = masterPriceList[temp_thisitemid]['buy']
            temp_thisentry = QTableWidgetItem(floatascurrency(temp_thisbuyprice))
            temp_thisentry.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            
            self.baseMatsTableWidget.setItem(rr, temp_unitbuypricecol, temp_thisentry)
      
        # add build fees to components table
        temp_namecol = self.matsTableWidget.findColByHeaderText(self.matsTableHeaders['name'])
        temp_buildfeetotalcol = self.matsTableWidget.findColByHeaderText(self.matsTableHeaders['buildfeetotal'])
        if not temp_buildfeetotalcol: temp_buildfeetotalcol = self.matsTableWidget.appendCol(self.matsTableHeaders['buildfeetotal'])

        for rr in range(0, self.matsTableWidget.rowCount()):
            temp_thisitemid = krabtools.auxdatatools.getitemid(self.matsTableWidget.item(rr,temp_namecol).text())
            temp_thisentry = QTableWidgetItem(floatascurrency(self.buildCosts['componentsBuildFees'][temp_thisitemid]))
            temp_thisentry.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                        
            self.matsTableWidget.setItem(rr, temp_buildfeetotalcol, temp_thisentry)

        QApplication.restoreOverrideCursor()

    def compareMatSellPrices(self):
        global masterPriceList
        QApplication.setOverrideCursor(QCursor(Qt.WaitCursor))

        updateMasterPriceList(self.baseMatsList, 'sell', 'Jita')

        temp_namecol, temp_unitbuypricecol = self.baseMatsTableWidget.findColByHeaderText(self.baseMatsTableHeaders['name']), self.baseMatsTableWidget.findColByHeaderText(self.baseMatsTableHeaders['unitbuy'])
        temp_quantitycol = self.baseMatsTableWidget.findColByHeaderText(self.baseMatsTableHeaders['qty'])
        temp_unitsellpricecol, temp_margindeltacol = self.baseMatsTableWidget.findColByHeaderText(self.baseMatsTableHeaders['unitsell']), self.baseMatsTableWidget.findColByHeaderText(self.baseMatsTableHeaders['margindelta'])
        
        if not temp_unitsellpricecol: temp_unitsellpricecol = self.baseMatsTableWidget.appendCol(self.baseMatsTableHeaders['unitsell'])
        if not temp_margindeltacol: temp_margindeltacol = self.baseMatsTableWidget.appendCol(self.baseMatsTableHeaders['margindelta'])

        for rr in range(0, self.baseMatsTableWidget.rowCount()):
            temp_thisitemid = krabtools.auxdatatools.getitemid(self.baseMatsTableWidget.item(rr,temp_namecol).text())
            temp_thisbuyprice = masterPriceList[temp_thisitemid]['buy']
            temp_thissellprice = masterPriceList[temp_thisitemid]['sell']
            temp_thisqty = self.baseMatsList[temp_thisitemid]
            temp_thisbuyfee = krabtools.evemarket.calcbuyfee((temp_thisbuyprice*temp_thisqty), 'buy', skillBrokerRelations=1)
            temp_thistotaldiff = (temp_thissellprice - (temp_thisbuyprice + temp_thisbuyfee/temp_thisqty)) * temp_thisqty
            temp_thismargindiff = temp_thistotaldiff / self.profitAbs * 100

            temp_thisentry_sellprice = QTableWidgetItem(floatascurrency(temp_thissellprice))
            temp_thisentry_sellprice.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)

            temp_thisentry_margindelta = QTableWidgetItem( str(round(temp_thismargindiff,1))+' %' )
            temp_thisentry_margindelta.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            
            self.baseMatsTableWidget.setItem(rr, temp_unitsellpricecol, temp_thisentry_sellprice)
            self.baseMatsTableWidget.setItem(rr, temp_margindeltacol, temp_thisentry_margindelta)
            
        if self.width() < self.matsWidget.width():
            self.resize(self.width() + self.matsWidget.width(), self.height())

        if self.inventmode:
            if krabtools.auxdatatools.ishullsection(self.inventtype):
                updateMasterPriceList(self.inventMatsPerBP, 'sell', 'Jita')
                self.inventCostPerBuySellMarginDiffLabel.setText('Buy/Sell margin delta: %s%%' % round((krabtools.indytools.get_matslist_cost_from_pricelist(self.inventMatsPerBP, masterPriceList, order_type='sell', return_type='total') * (1 / self.inventChance) * (1 / self.runsperBP) - self.inventcostperrun) * self.runstobuild / self.profitAbs * 100, 1))
            else:
                self.inventCostPerBuySellMarginDiffLabel.setText('Buy/Sell margin delta: N/A')

        QApplication.restoreOverrideCursor()

def floatascurrency(n, symbol=None):
    out = '{:20,.2f}'.format(n)
    if symbol: out = symbol + out
    return out

def currencystrasfloat(n):
    n = n.replace(',','')

    # catch any currency symbols at the start
    firstdigit = 0
    for cc in n:
        if not cc.isdigit():
            firstdigit += 1
        else:
            break

    n = n[firstdigit:]

    return n

def generateMatsTable(tableData, headers=None, showIcons=False, sort_enable=True, parent=None):
    if isinstance(tableData, dict): tableData = [(kk,vv) for kk,vv in tableData.items()]

    if not all(ii == len(tableData[0]) for ii in [len(jj) for jj in tableData]): raise Exception('Table rows not of constant length!')

    if showIcons:

        newTableData = []
        for rr, row in enumerate(tableData):
            newrow = list(row)
            newrow.insert(0, getIcon(krabtools.auxdatatools.getitemid(row[0]), 32))
            newTableData.append(newrow)

        tableData = newTableData
        del newTableData

        if not isinstance(headers, list): headers = list(headers)
        headers.insert(0, 'Icon')

    tempTable = TableWidgetWCopyPaste()
    tempTable.setColumnCount(len(tableData[0]))
    tempTable.setRowCount(len(tableData))

    tempTable.setSortingEnabled(False)

    if headers:
        if not (isinstance(headers, list) or isinstance(headers, tuple)): raise Exception('Invalid headers: %s, must be specified as list or tuple of strings' % headers)
        if len(headers) != tempTable.columnCount(): raise Exception('Wrong number of headers, expected %s but got %s' % (tempTable.columnCount(), len(headers)))

        for ii, header in enumerate(headers):
            tempTable.setHorizontalHeaderItem(ii, QTableWidgetItem(header))

    for rr, row in enumerate(tableData):
        for cc, val in enumerate(row):
            
            if showIcons and cc == 0:
                iconLabel = QLabel()
                iconPixmap = QPixmap(val)
                iconLabel.setPixmap(iconPixmap)
                iconLabel.setAlignment(Qt.AlignCenter)
                tempTable.setCellWidget(rr, cc, iconLabel)

            else:
                entry = QTableWidgetItem(str(val))
                entry.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                entry.setFlags(entry.flags() ^ Qt.ItemIsEditable)
                tempTable.setItem(rr, cc, entry)

    if sort_enable:
        tempTable.setSortingEnabled(True)
        tempTable.sortItems( (1 if showIcons else 0 ) )

    tempTable.resizeColumnsToContents()

    return tempTable

def loadBPProducts():
    global allBPProducts
    
    QApplication.setOverrideCursor(QCursor(Qt.WaitCursor))
    print('Loading available BP products...',end='')
    allBPProducts = krabtools.sqlitetools.getxbyyfromdb(krabtools.presets.auxdataDB, 'Items', 'typeName', 'Manufacturable', 1)
    print('done.')
    QApplication.restoreOverrideCursor()

def getIcon(iconID, size):
    basepath = './icons/ccp/items/'
    filename = krabtools.auxdatatools.geticonfilename(iconID, size)
    filepath = os.path.join(basepath, filename)

    if not os.path.exists(basepath): os.makedirs(basepath)
    if os.path.isfile(filepath):
        return filepath
    else:
        filepath = downloadIcon(iconID, size, basepath)
        return filepath

def downloadIcon(iconID, size, dlpath='./icons/ccp/items/'):
    iconPath = krabtools.downloadfile(krabtools.auxdatatools.geticonurl(iconID, size), dlpath)
    return iconPath

def deleteAllIcons(basepath='./icons/ccp/items/'):
    for filename in os.listdir(basepath):
        os.remove(os.path.join(basepath, filename))

def checkProduct(product):
    if not product:
        print('No product selected!')
        return False
    elif product not in allBPProducts:
        print('Invlaid product: %s' % product)
        return False
    else:
        return True

def saveMasterPriceList():
    global masterPriceList_hasBeenUpdated

    if not masterPriceList: # !TODO Add yes/no dialog box if price list is empty
        pass
    else:
        QApplication.setOverrideCursor(QCursor(Qt.WaitCursor))

        print('Saving market prices to %s...' % os.path.abspath(krabtools.presets.indypriceDB), end='')
        krabtools.evemarket.savepricelisttoDB(masterPriceList, krabtools.presets.indypriceDB)

        masterPriceList_hasBeenUpdated = False
        
        QApplication.restoreOverrideCursor()

def loadMasterPriceList():
    global masterPriceList, masterPriceList_hasBeenUpdated

    if not os.path.isfile(krabtools.presets.indypriceDB):
        print('Local price DB not found (%s)' % os.path.abspath(krabtools.presets.indypriceDB))
    
    else:
        QApplication.setOverrideCursor(QCursor(Qt.WaitCursor))

        print('Loading market prices from %s...' % os.path.abspath(krabtools.presets.indypriceDB), end='')
        masterPriceList = krabtools.evemarket.loadpricelistfromDB(krabtools.presets.indypriceDB)

        QApplication.restoreOverrideCursor()

    masterPriceList_hasBeenUpdated = False

def refreshMasterPriceList():
    global masterPriceList, masterPriceList_hasBeenUpdated

    QApplication.setOverrideCursor(QCursor(Qt.WaitCursor))

    print('Refreshing %s cached market prices...' % len(masterPriceList))
    masterPriceList = krabtools.evemarket.refreshpricelist(masterPriceList)

    masterPriceList_hasBeenUpdated = True
    
    QApplication.restoreOverrideCursor()

def updateMasterPriceList(items, order_type, location):
    global masterPriceList, masterPriceList_hasBeenUpdated
    masterPriceList_old = masterPriceList
    masterPriceList = krabtools.evemarket.addmissingitemstopricelist(items, masterPriceList, order_type, location)

    if masterPriceList != masterPriceList_old: masterPriceList_hasBeenUpdated = True

def clearMasterPriceList():
    global masterPriceList

    masterPriceList = {}

    print('Master price list cleared')

def deleteMasterPriceListDB():
    def checkIfSure():
        areYouSure = QMessageBox()
        areYouSure.setWindowTitle('Are you sure?')
        areYouSure.setText('Delete local price DB?')
        areYouSure.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        areYouSure.setDefaultButton(QMessageBox.No)
        retval = areYouSure.exec_()

        if retval == QMessageBox.Yes:
            return True
        else:
            return False

    if checkIfSure():
        krabtools.deleteindypriceDB()
        print('Local price DB deleted')

def efficiencylist(efficency_pct_list):
    # takes a string of % efficiency savings e.g. '2, 5' for 2% and 5% and returns them as a list of floats e.g. [0.02, 0.05]
    efflist = [int(ii.strip())/100 for ii in efficency_pct_list.split(',')] if efficency_pct_list else []
    return efflist

def doPlatformSpecificSetup():
    appid = 'krabtools.indyapp'
    system, release = platform.system(), platform.release()

    def setAppUserModelID(appid):
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(appid)

    if system == 'Windows':
        setAppUserModelID(appid)

if __name__ == '__main__':
    doPlatformSpecificSetup()

    krabtools.setverbosity(2)

    app = QApplication(sys.argv)

    IndyAppMain = IndyAppMain()

    sys.exit(app.exec_())