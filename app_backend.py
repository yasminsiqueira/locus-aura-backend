import os
import bcrypt
import jwt
from datetime import datetime, timedelta, timezone 
from pymongo import MongoClient
from bson import ObjectId
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
SECRET_KEY = os.getenv("SECRET_KEY")

class LocusAuraAuth:
    def __init__(self, client):
        self.db = client['locus_aura_db']
        self.users = self.db['users']
        # Garante que não haverá e-mails duplicados
        self.users.create_index("email", unique=True)

    def _generate_hash(self, password):
        """Gera o hash da senha usando Bcrypt para segurança nível Pro."""
        return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt(12)).decode('utf-8')

    def register(self, name, email, password):
        """Realiza o cadastro do usuário com senha criptografada."""
        try:
            user_doc = {
                "full_name": name, 
                "email": email.lower(),
                "password_hash": self._generate_hash(password),
                "role": "corretor", 
                "is_active": False,  # Começa inativo para fluxo de verificação
                "lgpd_consent": True,
                "created_at": datetime.now(timezone.utc)
            }
            return self.users.insert_one(user_doc)
        except Exception:
            return None

    def login(self, email, password):
        """
        Realiza o login validando credenciais e tratando divergências do banco.
        Resolve o Bug #1 (Erro 500) e Bug #2 (Inativos).
        """
        # 1. Busca o usuário
        user = self.users.find_one({"email": email.lower()})
        
        # 2. Blindagem contra registros antigos sem hash de senha
        if not user or "password_hash" not in user:
            return None

        try:
            # 3. Verificação de Senha
            if bcrypt.checkpw(password.encode('utf-8'), user["password_hash"].encode('utf-8')):
                
                # 4. Verificação de conta ativa (usa .get para evitar crash se o campo faltar)
                if not user.get("is_active", False):
                    return "inactive"
                
                # 5. RESOLUÇÃO CRÍTICA: Converte ObjectId para string antes de gerar o JWT
                user_id_str = str(user["_id"])
                
                # 6. Payload do Token
                payload = {
                    "u_id": user_id_str, 
                    "exp": datetime.now(timezone.utc) + timedelta(hours=2)
                }
                
                # 7. Retorno formatado (Trata 'full_name' ou 'nome' para compatibilidade)
                return {
                    "token": jwt.encode(payload, SECRET_KEY, algorithm="HS256"), 
                    "name": user.get("full_name", user.get("nome", "Usuário")), 
                    "id": user_id_str 
                }
        except Exception:
            # Evita erro 500 se o bcrypt encontrar um formato de senha inválido no banco
            return None
            
        return None

class PropertyManager:
    def __init__(self, client):
        self.db = client['locus_aura_db']
        self.properties = self.db['properties']

    def add_property(self, broker_id, title, desc, price, pet=False, swap=False):
        """Adiciona imóvel validando regra de preço positivo (Bug #6)."""
        if price <= 0:
            return None
        
        doc = {
            "broker_id": broker_id,
            "title": title,
            "description": desc,
            "price": price,
            "features": {"pet_friendly": pet, "permuta": swap},
            "created_at": datetime.now(timezone.utc)
        }
        return self.properties.insert_one(doc)

# Bloco de inicialização para testes locais
if __name__ == "__main__":
    client = MongoClient(MONGO_URI)
    auth = LocusAuraAuth(client)
    pm = PropertyManager(client)
    print("--- Locus Aura Backend: Online e Protegido ---")