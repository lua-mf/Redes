import socket
from datetime import datetime

HOST = 'localhost'
PORT = 50000

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.bind((HOST, PORT))
s.listen()
print(f"Servidor esperando conexão do cliente em {HOST}:{PORT}...")
conn, ender = s.accept()
print('Conectado em ', ender)

handshake = conn.recv(1024).decode()
print(f"Handshake recebido: {handshake}")

try:
    partes = handshake.split(',')
    modo_operacao = int(partes[0].split('=')[1])
    tamanho_max = int(partes[1].split('=')[1])
    modo_envio = int(partes[2].split('=')[1])
    qtd_pacotes = int(partes[3].split('=')[1])
    
    print(f"Modo de operação: {modo_operacao}, Tamanho máximo: {tamanho_max}, Modo de envio: {modo_envio}, Quantidade de pacotes: {qtd_pacotes}")
    
    conn.sendall("handshake_ok".encode())
    print("\nAguardando pacotes...\n")
    
    # Buffer para armazenar todo o conteúdo recebido
    buffer_completo = ""
    pacotes_processados = 0
    mensagem_completa = ""  # Variável para reconstruir/armazenar a mensagem completa
    
    while pacotes_processados < qtd_pacotes:
        # Recebendo dados
        dados = conn.recv(1024).decode()
        
        if not dados:  # Se não receber nada, a conexão é fechada
            break
            
        buffer_completo += dados
        
        # Processa pacotes completos do buffer
        while buffer_completo and pacotes_processados < qtd_pacotes:
            # Extrai um pacote de acordo com o tamanho máximo
            pacote = buffer_completo[:tamanho_max]
            
            # Se não tem dados suficientes, aguarda mais
            if len(pacote) < min(tamanho_max, 1) and len(buffer_completo) < tamanho_max:
                break
                
            # Remove o pacote processado do buffer
            buffer_completo = buffer_completo[len(pacote):]
            
            # Adiciona à variável mensagem_completa
            mensagem_completa += pacote
            
            pacotes_processados += 1
            horario = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            
            print(f"Pacote {pacotes_processados} recebido:")
            print(f"- Conteúdo: '{pacote}'")
            print(f"- Tamanho: {len(pacote)}")
            print(f"- Horário: {horario}")
            print("---------------------------")
    
    print(f"\nMensagem completa reconstruída: '{mensagem_completa}'")
    
except Exception as e:
    print(f"Erro ao processar: {e}")
finally:
    conn.close()
    print("Conexão encerrada com o cliente.")