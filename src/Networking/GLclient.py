import sys
from Models.GLModels import GLPlayerList, GLGameList
from ThriftGameLobby.ttypes import GLPlayer
from Networking.EventBasedClient import EventBasedClient
import settingsManager
sys.path.append('gen-py')

from ThriftGameLobby import TGameLobby
from util import utilities

class Client(EventBasedClient):
    def __init__(self, delegate):
        print "Initializing game lobby client..."
        EventBasedClient.__init__(self, TGameLobby.Client, settingsManager.settings['hostname'], 42141, delegate)

        self.listeners = {}

        self.playerModel = None
        self.gameModel = None

        self.playerIDIgnores.append('removeGame')
        self.gameID = -1 # for when in a draft

        self.addMapping('addPlayer', self.eventAddPlayer)
        self.addMapping('addGame', self.eventAddGame)
        self.addMapping('removeGame', self.eventRemoveGame)
        self.addMapping('removePlayer', self.eventRemovePlayer)
        self.addMapping('playerJoinedGame', self.eventPlayerJoinedGame)
        self.addMapping('playerLeftGame', self.eventPlayerLeftGame)
        self.addMapping('gameStarted', self.eventGameStarted)
        self.addMapping('expansionPassedTo', self.eventExpansionPassedTo)
        self.addMapping('playerSwitchedTeams', self.eventPlayerSwitchedTeams)

    def eventExpansionPassedTo(self, event):
        if int(event.data[1]) is not self.playerID or int(event.data[2]) is not self.gameID:
            return
        try:
            listener = self.listeners[int(event.data[2])]
            listener.expansionPassedToMe(event.data[0], event.senderName)
        except IndexError:
            return

    def eventGameStarted(self, event):
        gameID = int(event.data[0])
        try:
            listener = self.listeners[gameID]
            listener.startGame()
        except IndexError:
            print "Listener does not exist"
        except KeyError:
            print "Listener does not exist"
        game = self.gameModel.gameForID(gameID)
        index = self.gameModel.list.index(game)
        self.gameModel.setItem(self.client.GLgetGame(gameID), index)

    def eventAddPlayer(self, event):
        player = GLPlayer()
        player.playerID = event.sender
        player.playerName = event.data[0]
        player.currentGameID = -1
        player.team = 0
        self.playerModel.addItem(player)

    def eventAddGame(self, event):
        self.gameModel.addItem(self.client.GLgetGame(int(event.data[0])))

    def eventRemoveGame(self, event):
        try:
            # If the in-game dialog is open, cancel it
            gameID = int(event.data[0])
            listener = self.listeners[gameID]
            listener.gameWasCanceled()
            if listener.deletesListener:
                del self.listeners[gameID]
        except IndexError:
            pass
        self.gameModel.removeGameWithID(int(event.data[0]))

    def eventRemovePlayer(self, event):
        self.playerModel.removePlayerWithID(event.sender)

    def eventPlayerJoinedGame(self, event):
        try:
            gameID = int(event.data[0])
            listener = self.listeners[gameID]

            player = self.playerModel.playerForID(event.sender)
            player.currentGameID = gameID
            game = self.gameModel.gameForID(gameID)
            game.players.append(player)

            listener.addPlayer(player)
        except IndexError:
            pass
        except KeyError:
            pass

    def eventPlayerLeftGame(self, event):
        try:
            gameID = int(event.data[0])
            listener = self.listeners[gameID]

            player = self.playerModel.playerForID(event.sender)
            player.currentGameID = -1
            game = self.gameModel.gameForID(gameID)
            game.players.remove(player)
            listener.removePlayer(player)
        except IndexError:
            pass
        except ValueError:
            pass
        except KeyError:
            pass

    def eventPlayerSwitchedTeams(self, event):
        try:
            gameID = int(event.data[0])
            listener = self.listeners[gameID]
            player = self.playerModel.playerForID(event.sender)
            player.team = int(event.data[1])
            listener.teamChangedForPlayer(player)
        except IndexError:
            pass
        except KeyError:
            pass

    ###################################################
    ### Functions called by the client program ########
    ### Not event-based ###############################
    ###################################################

    def register(self, username):
        '''Registers the player with the server. The player is added to the list of players, the client recieves a playerID, and the username that player chooses carries through all their games.'''
        self.username = username
        self.playerID = self.client.GLregisterPlayer(username)
        print "ID: %d" % (self.playerID)

        self.playerModel = GLPlayerList(self.playerID, self)
        self.gameModel = GLGameList(self)
        self.playerModel.list = self.client.GLgetPlayersInLobby()
        self.gameModel.list = self.client.GLgetGames()

        self.lastEventIndex = self.client.GLcurrentEventIndex()

        # Don't start runLoop until playerID is gained
        self.startEventLoop(self.client.GLgetEvents)

    def createGame(self, gameName, gameType, expansions):
        game = self.client.GLnewGame(self.playerID, gameName, gameType, expansions)
        self.gameModel.addItem(game)
        return game

    def disconnect(self):
        '''Called when the program exits. Alerts the server that the player is gone.'''
        self.client.GLunregisterPlayer(self.playerID)
        self.transport.close()

    def getGames(self):
        return self.client.GLgetGames()

    def joinGame(self, game):
        return self.client.GLrequestToJoinGame(self.playerID, game.gameID)

    def cancelGame(self, game):
        self.client.GLcancelGame(self.playerID, game)

    def startGame(self, game):
        self.client.GLstartGame(game.gameID)

    def switchToTeam(self, gameID, team):
        self.client.GLswitchToTeam(self.playerID, gameID, team)

    def gameWithIndex(self, index):
        return self.client.GLgetGame(index)

    def registerListenerForGame(self, listener, game):
        self.listeners[game.gameID] = listener

    def removeListenersForGame(self, game):
        print "Removing listeners for game %s" % (game.gameID)
        try:
            del self.listeners[game.gameID]
        except:
            pass

    def joinDraft(self, gameID):
        self.gameID = gameID

    def passExpansion(self, expansion):
        self.client.GLpassExpansion(self.gameID, self.playerID, expansion)
