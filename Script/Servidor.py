import socket

HOST = 'localhost'
PORT = 50000

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.bind((HOST, PORT))
s.listen()

print(f"Servidor esperando conexão do cliente em {HOST}:{PORT}...")
conn, ender = s.accept()

print('Conectado em ', ender)

while True:
    handshake = conn.recv(1024).decode()

    if not handshake:
        print('Fechando a conexão')
        conn.close()
        break

    print(f"Handshake recebido: {handshake}")

    try:
        partes = handshake.split(',')
        modo_operacao = int(partes[0].split('=')[1])
        tamanho_max = int(partes[1].split('=')[1])
        print(f"Modo de operação: {modo_operacao}, Tamanho máximo: {tamanho_max}")
        
        conn.sendall("handshake_ok".encode())

    except IndexError as e:
        print(f"Erro ao processar handshake: {e}")
        break
    except ValueError as e:
        print(f"Erro de conversão: {e}")
        break
