import json
import os
import pickle
import math
import collections
import re

class AdvancedLocalRAG:
    """
    Advanced TF-IDF (BM25) Local Vector DB.
    Now indexes faces, state changes, and conditions for context-rich retrieval.
    """
    def __init__(self, index_path):
        self.index_path = index_path
        self.documents = [] 
        self.doc_lengths = []
        self.avg_doc_len = 0
        self.df = collections.defaultdict(int) 
        self.tf = [] 
        self.vocab = set()
        
    def _tokenize(self, text):
        return re.findall(r'\w+', text.lower())

    def build_index(self, scenes_file):
        print(f"Building Advanced RAG Index from {scenes_file}...")
        with open(scenes_file, "r", encoding="utf-8") as f:
            self.documents = json.load(f)
            
        total_len = 0
        for doc in self.documents:
            # Combine text, faces, and conditions to form the indexable payload
            combined_text = doc["text"] + " " + " ".join(doc.get("faces_used", [])) + " " + " ".join(doc.get("state_changes", []))
            
            tokens = self._tokenize(combined_text)
            doc_len = len(tokens)
            self.doc_lengths.append(doc_len)
            total_len += doc_len
            
            tf_counter = collections.Counter(tokens)
            self.tf.append(tf_counter)
            
            for term in tf_counter.keys():
                self.df[term] += 1
                self.vocab.add(term)
                
        if self.documents:
            self.avg_doc_len = total_len / len(self.documents)
            
        self.save_index()
        print(f"Advanced RAG Index built successfully with {len(self.documents)} scenes.")

    def save_index(self):
        os.makedirs(os.path.dirname(self.index_path), exist_ok=True)
        with open(self.index_path, "wb") as f:
            pickle.dump({
                "documents": self.documents,
                "doc_lengths": self.doc_lengths,
                "avg_doc_len": self.avg_doc_len,
                "df": self.df,
                "tf": self.tf
            }, f)

    def load_index(self):
        if not os.path.exists(self.index_path):
            return False
        with open(self.index_path, "rb") as f:
            data = pickle.load(f)
            self.documents = data["documents"]
            self.doc_lengths = data["doc_lengths"]
            self.avg_doc_len = data["avg_doc_len"]
            self.df = data["df"]
            self.tf = data["tf"]
        return True

    def query(self, query_text, top_k=3, k1=1.5, b=0.75):
        if not self.documents:
            if not self.load_index():
                raise ValueError("Index not found. Call build_index() first.")

        query_tokens = self._tokenize(query_text)
        scores = [0.0] * len(self.documents)
        N = len(self.documents)

        for token in query_tokens:
            if token not in self.df:
                continue
            
            idf = math.log(1 + (N - self.df[token] + 0.5) / (self.df[token] + 0.5))
            
            for doc_id in range(N):
                f_doc = self.tf[doc_id].get(token, 0)
                if f_doc == 0:
                    continue
                
                doc_len = self.doc_lengths[doc_id]
                numerator = f_doc * (k1 + 1)
                denominator = f_doc + k1 * (1 - b + b * (doc_len / self.avg_doc_len))
                
                scores[doc_id] += idf * (numerator / denominator)

        top_indices = sorted(range(N), key=lambda i: scores[i], reverse=True)[:top_k]
        
        results = []
        for idx in top_indices:
            if scores[idx] > 0:
                results.append({
                    "score": scores[idx],
                    "document": self.documents[idx]
                })
                
        return results

if __name__ == "__main__":
    base_dir = r"d:\Agentic Translation Framework (ATF) Project\data\tlas"
    scenes_path = os.path.join(base_dir, "rpgm_scenes_v4.json")
    index_path = os.path.join(base_dir, "rag_index_v4.pkl")
    
    rag = AdvancedLocalRAG(index_path)
    
    if not os.path.exists(index_path):
        rag.build_index(scenes_path)
    else:
        rag.load_index()
        print(f"Loaded existing RAG Index with {len(rag.documents)} scenes.")
        
    test_q = "Shion talks about Bakery and custard or whipped cream"
    print(f"\n--- Testing Advanced RAG Query: '{test_q}' ---")
    results = rag.query(test_q, top_k=2)
    
    for r in results:
        print(f"\n[Score: {r['score']:.2f}] Source: {r['document']['source']}")
        print(f"Conditions: {r['document']['conditions']}")
        print(f"State Changes (Switches/Vars): {r['document']['state_changes']}")
        print(f"Faces/Sprites used: {r['document']['faces_used']}")
        print(f"Text Snippet: {r['document']['text'][:200]}...")
