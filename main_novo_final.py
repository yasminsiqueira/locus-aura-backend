import os
import certifi
from typing import List, Optional
from datetime import datetime
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pymongo import MongoClient
from pydantic import BaseModel, Field, field_validator
import re
from bson import ObjectId
from app_backend import LocusAuraAuth, PropertyManager

load_dotenv()
MONGO_URI = os.getenv("MONGO_URI")

app = FastAPI(title="Locus Aura - Ecossistema Imobiliário Oficial")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

client = MongoClient(MONGO_URI, tlsCAFile=certifi.where())
db = client['locus_aura_db']

auth_service = LocusAuraAuth(client)
property_service = PropertyManager(client)

def validar_email_generico(v: str):
    if not re.match(r"[^@]+@[^@]+\.[^@]+", v):
        raise ValueError('E-mail inválido')
    return v.lower()

# ══════════════════════════════════════════════
# MODELOS
# ══════════════════════════════════════════════

class LoginData(BaseModel):
    email: str
    password: str
    _validate_email = field_validator('email')(validar_email_generico)

class UserSignup(BaseModel):
    nome: str
    email: str
    password: str
    role: str
    creci: Optional[str] = None
    is_active: bool = False
    _validate_email = field_validator('email')(validar_email_generico)

class VerifyCode(BaseModel):
    email: str
    code: str
    _validate_email = field_validator('email')(validar_email_generico)

class LeadData(BaseModel):
    nome: str
    telefone: str
    email: str
    mensagem: Optional[str] = "Interesse via site"
    imovel_id: Optional[str] = None
    corretor_id: str
    status: str = "Novo"
    origem: str = "Site"
    _validate_email = field_validator('email')(validar_email_generico)

class ImovelData(BaseModel):
    titulo: str
    descricao: str
    localizacao: str
    preco: float = Field(..., gt=0)
    condominio: Optional[float] = 0.0
    finalidade: str
    tipo_imovel: str
    tamanho_m2: float
    quartos: int
    suites: int
    banheiros: int
    vagas: int
    salas: int
    cozinhas: int
    varandas: int
    andares: Optional[int] = 1
    area_lazer: bool = False
    aceita_pets: bool = False
    fotos: List[str] = []
    corretor_id: str

class FavoriteAction(BaseModel):
    user_id: str
    imovel_id: str

class ClientListing(BaseModel):
    cliente_id: str
    cliente_nome: Optional[str] = ""
    cliente_email: Optional[str] = ""
    cliente_telefone: Optional[str] = ""
    status: str = "pendente"
    titulo: str
    descricao: str
    localizacao: str
    preco: float = Field(..., gt=0)
    condominio: Optional[float] = 0.0
    finalidade: str
    tipo_imovel: str
    tamanho_m2: float
    quartos: int
    suites: int
    banheiros: int
    vagas: int
    salas: int
    cozinhas: int
    varandas: int
    andares: Optional[int] = 1
    area_lazer: bool = False
    aceita_pets: bool = False
    fotos: List[str] = []
    criado_em: Optional[str] = None

class UpdateProfile(BaseModel):
    nome: Optional[str] = None
    email: Optional[str] = None
    password: Optional[str] = None
    creci: Optional[str] = None
    telefone: Optional[str] = None
    foto: Optional[str] = None

class KanbanCard(BaseModel):
    lead_id: str
    corretor_id: str
    etapa: str = "Leads Frios"
    prioridade: int = 1
    notas_internas: Optional[str] = ""

class DealData(BaseModel):
    titulo_negocio: str
    valor_transacao: float = Field(..., gt=0)
    etapa: str
    proximo_passo: str
    data_interacao: str
    descricao: str
    comissao_estimada: float
    corretor_id: str

# ══════════════════════════════════════════════
# ROTAS ORIGINAIS (mantidas intactas)
# ══════════════════════════════════════════════

@app.get("/")
def read_root():
    return {"status": "Locus Aura API Online", "database": "Conectado"}

@app.get("/imoveis", response_model=List[dict])
def listar_imoveis():
    imoveis = list(db.imoveis.find())
    for item in imoveis:
        item["_id"] = str(item["_id"])
    return imoveis

@app.get("/imoveis/busca-ia")
def busca_ia(pergunta: str):
    try:
        import requests
        import re
        from bson import ObjectId
        import os
        
        # Puxa a chave da Groq que você acabou de configurar no Render
        api_key = os.getenv("AI_API_KEY")
        
        # URL e Modelo oficiais da Groq
        url = "https://api.groq.com/openai/v1/chat/completions"
        modelo = "llama-3.1-8b-instant"" 
        
        # Busca todos os imóveis no banco de dados
        todos_imoveis = list(db.imoveis.find({}))
        
        prompt = f"""
        Você é o assistente Locus Aura. Analise a seguinte lista de imóveis: {str(todos_imoveis)}
        O usuário busca por: "{pergunta}"
        Retorne APENAS uma lista JSON com os códigos '_id' dos imóveis que melhor atendem ao pedido.
        Exemplo: ["id1", "id2"]. Se não houver nenhum, retorne [].
        """
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        
        payload = {
            "model": modelo,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1 # Temperatura baixa para a IA ser precisa e não inventar dados
        }
        
        # Envia a requisição direta para a Groq
        resposta = requests.post(url, headers=headers, json=payload)
        dados = resposta.json()
        
        # Se a Groq bloquear ou der erro de chave, avisa na tela
        if "error" in dados:
            return {"mensagem_ia": f"Erro na IA: {dados['error']['message']}", "resultados": []}
            
        # Pega a resposta da IA
        texto_ia = dados['choices'][0]['message']['content']
        
        # Filtra apenas os IDs válidos do MongoDB
        ids_limpos = re.findall(r'[a-f0-9]{24}', texto_ia)
        ids_objetos = [ObjectId(id) for id in ids_limpos]
        
        # Retorna os imóveis filtrados
        resultados = list(db.imoveis.find({"_id": {"$in": ids_objetos}}))
        for r in resultados: r["_id"] = str(r["_id"])
        
        msg = "Encontrei estas opções no Locus Aura para você!" if resultados else "Não encontrei imóveis com essas exatas características."
        return {"mensagem_ia": msg, "resultados": resultados}

    except Exception as e:
        return {"mensagem_ia": f"Erro interno do Python: {str(e)}", "resultados": []}

@app.post("/login")
def login(data: LoginData):
    user = auth_service.login(data.email, data.password)
    if user == "inactive":
        raise HTTPException(status_code=403, detail="Conta inativa. Verifique seu e-mail.")
    if not user:
        raise HTTPException(status_code=401, detail="E-mail ou senha incorretos")
    return user

@app.post("/signup")
def signup(user: UserSignup):
    if db.users.find_one({"email": user.email.lower()}):
        raise HTTPException(status_code=400, detail="E-mail já cadastrado")
    res = auth_service.register(user.nome, user.email, user.password)
    if not res:
        raise HTTPException(status_code=500, detail="Erro interno ao criar conta")
    db.verifications.insert_one({
        "email": user.email.lower(),
        "code": "123456",
        "criado_em": datetime.now()
    })
    return {"status": "Usuário criado! Use 123456 para ativar."}

@app.post("/verify")
def verify_email(data: VerifyCode):
    if data.code == "123456":
        res = db.users.update_one(
            {"email": data.email.lower()},
            {"$set": {"is_active": True}}
        )
        if res.matched_count == 0:
            raise HTTPException(status_code=404, detail="E-mail não encontrado")
        return {"status": "Conta ativada!"}
    raise HTTPException(status_code=400, detail="Código inválido")

@app.put("/perfil/{user_id}")
def atualizar_perfil(user_id: str, dados: UpdateProfile):
    update_data = {k: v for k, v in dados.dict().items() if v is not None}
    if not update_data:
        raise HTTPException(status_code=400, detail="Nenhum dado para atualizar")
    try:
        res = db.users.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": update_data}
        )
        if res.matched_count == 0:
            raise HTTPException(status_code=404, detail="Usuário não encontrado")
        return {"status": "Perfil atualizado com sucesso"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.delete("/perfil/{user_id}")
def eliminar_conta(user_id: str):
    try:
        db.users.delete_one({"_id": ObjectId(user_id)})
        db.favorites.delete_many({"user_id": user_id})
        db.leads.delete_many({"corretor_id": user_id})
        return {"status": "Dados excluídos com sucesso"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/favoritos/{user_id}")
def listar_favoritos(user_id: str):
    favs = list(db.favorites.find({"user_id": user_id}))
    for f in favs:
        f["_id"] = str(f["_id"])
    return favs

@app.post("/favoritos/toggle")
def toggle_favorito(action: FavoriteAction):
    q = {"user_id": action.user_id, "imovel_id": action.imovel_id}
    if db.favorites.find_one(q):
        db.favorites.delete_one(q)
        return {"status": "removido"}
    db.favorites.insert_one(q)
    return {"status": "adicionado"}

@app.post("/anuncios-cliente/enviar")
def enviar_anuncio_cliente(data: ClientListing):
    doc = data.dict()
    doc["criado_em"] = datetime.now().isoformat()
    res = db.client_listings.insert_one(doc)
    return {"status": "sucesso", "id": str(res.inserted_id)}

@app.get("/corretores")
def listar_especialistas():
    especialistas = list(db.brokers.find({"is_active": True}))
    for e in especialistas:
        e["_id"] = str(e["_id"])
    return especialistas

@app.get("/dashboard/resumo/{corretor_id}")
def get_dashboard_summary(corretor_id: str):
    return {
        "total_leads": db.leads.count_documents({"corretor_id": corretor_id}),
        "novos_leads": db.leads.count_documents({"corretor_id": corretor_id, "status": "Novo"}),
        "imoveis_ativos": db.imoveis.count_documents({"corretor_id": corretor_id}),
        "anuncios_pendentes": db.client_listings.count_documents({"status": "pendente"})
    }

@app.get("/leads/lista/{corretor_id}")
def listar_leads_agenda(corretor_id: str, busca: Optional[str] = None):
    query = {"corretor_id": corretor_id}
    if busca:
        query["nome"] = {"$regex": busca, "$options": "i"}
    leads = list(db.leads.find(query).sort("_id", -1))
    for l in leads:
        l["_id"] = str(l["_id"])
    return leads

@app.post("/leads/enviar")
def enviar_lead(lead: LeadData):
    doc = lead.dict()
    doc["criado_em"] = datetime.now().isoformat()
    db.leads.insert_one(doc)
    return {"status": "Mensagem recebida"}

@app.post("/kanban/criar-card")
def criar_card_kanban(data: KanbanCard):
    res = db.kanban_cards.insert_one(data.dict())
    return {"id": str(res.inserted_id)}

@app.put("/kanban/card/{card_id}")
def atualizar_card_kanban(card_id: str, dados_card: dict):
    try:
        db.kanban_cards.update_one(
            {"_id": ObjectId(card_id)},
            {"$set": dados_card}
        )
        return {"status": "Card atualizado"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.delete("/kanban/card/{card_id}")
def excluir_card_kanban(card_id: str):
    try:
        db.kanban_cards.delete_one({"_id": ObjectId(card_id)})
        return {"status": "Card excluído com sucesso"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/kanban/board/{corretor_id}")
def listar_cards_kanban(corretor_id: str):
    cards = list(db.kanban_cards.find({"corretor_id": corretor_id}))
    for c in cards:
        c["_id"] = str(c["_id"])
        try:
            lead = db.leads.find_one({"_id": ObjectId(c["lead_id"])})
            c["nome_lead"] = lead["nome"] if lead else "Lead Excluído"
        except:
            c["nome_lead"] = "Lead Excluído"
    return cards

@app.get("/deals/{corretor_id}")
def listar_negocios(corretor_id: str):
    deals = list(db.deals.find({"corretor_id": corretor_id}))
    for d in deals:
        d["_id"] = str(d["_id"])
    return deals

@app.get("/comissao/calcular")
def calcular_comissao(valor_venda: float):
    total = valor_venda * 0.05
    return {
        "valor_venda": valor_venda,
        "comissao_total": round(total, 2),
        "imobiliaria": round(total * 0.40, 2),
        "ganho_corretor": round(total * 0.30, 2)
    }

# ══════════════════════════════════════════════
# NOVOS ENDPOINTS
# ══════════════════════════════════════════════

# NOVO 1: Corretor publica imóvel no banco (aparece no site)
@app.post("/imoveis")
def publicar_imovel(data: ImovelData):
    doc = data.dict()
    doc["criado_em"] = datetime.now().isoformat()
    doc["publicado"] = True
    res = db.imoveis.insert_one(doc)
    return {"status": "Imóvel publicado com sucesso!", "id": str(res.inserted_id)}

# NOVO 2: Listar anúncios enviados por clientes (para a área do corretor)
@app.get("/anuncios-cliente/lista")
def listar_anuncios_clientes(status: Optional[str] = None):
    query = {}
    if status:
        query["status"] = status
    listings = list(db.client_listings.find(query).sort("_id", -1))
    for l in listings:
        l["_id"] = str(l["_id"])
    return listings

# NOVO 3: Corretor aprova/rejeita anúncio de cliente
@app.put("/anuncios-cliente/{listing_id}/status")
def atualizar_status_anuncio(listing_id: str, status: str):
    try:
        db.client_listings.update_one(
            {"_id": ObjectId(listing_id)},
            {"$set": {"status": status}}
        )
        return {"status": f"Anúncio marcado como {status}"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# NOVO 4: Buscar dados do usuário pelo ID (para preencher perfil)
@app.get("/perfil/{user_id}")
def buscar_perfil(user_id: str):
    try:
        user = db.users.find_one({"_id": ObjectId(user_id)})
        if not user:
            raise HTTPException(status_code=404, detail="Usuário não encontrado")
        user["_id"] = str(user["_id"])
        user.pop("password_hash", None)  # nunca retornar a senha
        return user
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# NOVO 5: Buscar imóveis de um corretor específico
@app.get("/imoveis/corretor/{corretor_id}")
def imoveis_do_corretor(corretor_id: str):
    imoveis = list(db.imoveis.find({"corretor_id": corretor_id}))
    for im in imoveis:
        im["_id"] = str(im["_id"])
    return imoveis
