import asyncio
import socketio

async def main():
    # Initialisation du client
    sio = socketio.AsyncClient()

    @sio.event
    async def connect():
        print("Connecté au serveur !")
        # Option 1 : Envoyer une donnée dès la connexion
        await asyncio.sleep(3)
        await sio.emit('message', {'data': 'Hello Server'}, namespace="/")

    @sio.event
    async def disconnect():
        print("Déconnecté du serveur")
        
    @sio.event(namespace="/")
    async def response(data):
        print("Data", data)
        
    @sio.on("*", namespace="/")
    async def handle_response(data):
        print("Data", data)


    # Connexion au serveur (ajustez l'URL)
    await sio.connect('http://localhost:8000')
    
    # Option 2 : Envoyer une donnée après la connexion
    await sio.emit('chat', 'Ceci est un test', namespace="/")
    
    # Garde la connexion ouverte pour écouter les réponses
    await sio.wait()

if __name__ == '__main__':
    asyncio.run(main())
