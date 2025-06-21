#!/usr/bin/env python3
"""
TELJES MEGOLDÁS - User Study with CSV Processing + Images
A `processed_recipes.csv` létrehozása és használata
"""

import os
import sys
import sqlite3
import datetime
import random
import pandas as pd
import numpy as np
from pathlib import Path
from flask import Blueprint, render_template, request, session, redirect, url_for, jsonify

# Project path setup
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Blueprint - TEMPLATE PATH FIX
user_study_bp = Blueprint('user_study', __name__, 
                         url_prefix='',
                         template_folder='templates/user_study')

class UserStudyDatabase:
    """Adatbázis kezelő"""
    
    def __init__(self, db_path="user_study.db"):
        self.db_path = db_path
        self.init_database()
    
    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def init_database(self):
        conn = self.get_connection()
        
        # Participants
        conn.execute('''
            CREATE TABLE IF NOT EXISTS participants (
                user_id INTEGER PRIMARY KEY AUTOINCREMENT,
                age_group TEXT NOT NULL,
                education TEXT NOT NULL,
                cooking_frequency TEXT NOT NULL,
                sustainability_awareness INTEGER NOT NULL,
                version TEXT NOT NULL,
                is_completed BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Interactions
        conn.execute('''
            CREATE TABLE IF NOT EXISTS interactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                recipe_id INTEGER,
                rating INTEGER,
                explanation_helpful INTEGER,
                view_time_seconds REAL,
                interaction_order INTEGER,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES participants (user_id)
            )
        ''')
        
        # Questionnaire
        conn.execute('''
            CREATE TABLE IF NOT EXISTS questionnaire (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                system_usability INTEGER,
                recommendation_quality INTEGER,
                trust_level INTEGER,
                explanation_clarity INTEGER,
                sustainability_importance INTEGER,
                overall_satisfaction INTEGER,
                additional_comments TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES participants (user_id)
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def create_user(self, age_group, education, cooking_frequency, sustainability_awareness, version):
        conn = self.get_connection()
        cursor = conn.execute('''
            INSERT INTO participants (age_group, education, cooking_frequency, sustainability_awareness, version)
            VALUES (?, ?, ?, ?, ?)
        ''', (age_group, education, cooking_frequency, sustainability_awareness, version))
        
        user_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return user_id
    
    def log_interaction(self, user_id, recipe_id, rating, explanation_helpful=None, view_time=None, interaction_order=None):
        conn = self.get_connection()
        conn.execute('''
            INSERT INTO interactions (user_id, recipe_id, rating, explanation_helpful, view_time_seconds, interaction_order)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (user_id, recipe_id, rating, explanation_helpful, view_time, interaction_order))
        conn.commit()
        conn.close()
    
    def save_questionnaire(self, user_id, responses):
        conn = self.get_connection()
        conn.execute('''
            INSERT INTO questionnaire 
            (user_id, system_usability, recommendation_quality, trust_level, 
             explanation_clarity, sustainability_importance, overall_satisfaction, additional_comments)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            user_id,
            responses.get('system_usability'),
            responses.get('recommendation_quality'),
            responses.get('trust_level'),
            responses.get('explanation_clarity'),
            responses.get('sustainability_importance'),
            responses.get('overall_satisfaction'),
            responses.get('additional_comments', '')
        ))
        
        conn.execute('UPDATE participants SET is_completed = TRUE WHERE user_id = ?', (user_id,))
        conn.commit()
        conn.close()

class CSVProcessor:
    """CSV feldolgozó és processed_recipes.csv létrehozó"""
    
    @staticmethod
    def create_processed_csv():
        """Létrehozza a processed_recipes.csv fájlt ha nem létezik"""
        processed_path = project_root / "data" / "processed_recipes.csv"
        
        # Ha már létezik, ne írjuk felül
        if processed_path.exists():
            print(f"✅ processed_recipes.csv már létezik: {processed_path}")
            return processed_path
        
        print("🔧 processed_recipes.csv létrehozása...")
        
        # Data mappa létrehozása
        os.makedirs(processed_path.parent, exist_ok=True)
        
        # Először próbáljuk a hungarian_recipes_github.csv-t
        original_csv = project_root / "hungarian_recipes_github.csv"
        
        if original_csv.exists():
            print(f"📊 Eredeti CSV feldolgozása: {original_csv}")
            return CSVProcessor.process_original_csv(original_csv, processed_path)
        else:
            print("⚠️ hungarian_recipes_github.csv nem található, sample CSV létrehozása")
            return CSVProcessor.create_sample_csv(processed_path)
    
    @staticmethod
    def process_original_csv(original_path, output_path):
        """Eredeti CSV feldolgozása"""
        try:
            # Többféle encoding próbálása
            encodings = ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252']
            df = None
            
            for encoding in encodings:
                try:
                    df = pd.read_csv(original_path, encoding=encoding)
                    print(f"✅ CSV betöltve {encoding} encoding-gal")
                    break
                except UnicodeDecodeError:
                    continue
            
            if df is None:
                print("❌ CSV betöltés sikertelen, sample adatok")
                return CSVProcessor.create_sample_csv(output_path)
            
            print(f"📋 Eredeti CSV: {len(df)} recept, oszlopok: {list(df.columns)}")
            
            # Oszlop mapping
            column_mapping = {
                'name': 'title',
                'ingredients': 'ingredients',
                'instructions': 'instructions',
                'images': 'images',
                'env_score': 'env_score_raw',
                'nutri_score': 'nutri_score_raw',
                'meal_score': 'meal_score_raw'
            }
            
            # Rename columns
            df = df.rename(columns=column_mapping)
            
            # Recipe ID hozzáadása
            df['recipeid'] = range(1, len(df) + 1)
            
            # Scores normalizálása
            df = CSVProcessor.normalize_scores(df)
            
            # Sample választás (50 recept)
            sample_size = min(50, len(df))
            df_sample = df.sample(n=sample_size)
            
            # Mentés
            df_sample.to_csv(output_path, index=False, encoding='utf-8')
            print(f"✅ Processed CSV mentve: {output_path} ({len(df_sample)} recept)")
            
            return output_path
            
        except Exception as e:
            print(f"❌ CSV feldolgozási hiba: {e}")
            return CSVProcessor.create_sample_csv(output_path)
    
    @staticmethod
    def normalize_scores(df):
        """Score-ok normalizálása 0-100 skálára"""
        
        # Environmental Score - inverz (kisebb = jobb környezetileg)
        if 'env_score_raw' in df.columns:
            env_min, env_max = df['env_score_raw'].min(), df['env_score_raw'].max()
            df['ESI'] = 100 - ((df['env_score_raw'] - env_min) / (env_max - env_min) * 100)
        else:
            df['ESI'] = 70.0  # default
        
        # Health Score - direkt (nagyobb = jobb)
        if 'nutri_score_raw' in df.columns:
            nutri_max = df['nutri_score_raw'].max()
            if nutri_max > 100:
                df['HSI'] = (df['nutri_score_raw'] / nutri_max) * 100
            else:
                df['HSI'] = df['nutri_score_raw']
        else:
            df['HSI'] = 75.0  # default
        
        # Popularity Score - direkt (nagyobb = népszerűbb)
        if 'meal_score_raw' in df.columns:
            meal_max = df['meal_score_raw'].max()
            if meal_max > 100:
                df['PPI'] = (df['meal_score_raw'] / meal_max) * 100
            else:
                df['PPI'] = df['meal_score_raw']
        else:
            df['PPI'] = 80.0  # default
        
        # Composite score
        df['composite_score'] = (df['ESI'] * 0.4 + df['HSI'] * 0.4 + df['PPI'] * 0.2)
        
        print(f"📊 Score tartományok:")
        print(f"   HSI: {df['HSI'].min():.1f} - {df['HSI'].max():.1f}")
        print(f"   ESI: {df['ESI'].min():.1f} - {df['ESI'].max():.1f}")
        print(f"   PPI: {df['PPI'].min():.1f} - {df['PPI'].max():.1f}")
        
        return df
    
    @staticmethod
    def create_sample_csv(output_path):
        """Sample CSV létrehozása ha nincs eredeti"""
        print("🔧 Sample CSV létrehozása külső képekkel...")
        
        sample_recipes = [
            {
                'recipeid': 1,
                'title': 'Hagyományos Gulyásleves',
                'ingredients': 'marhahús, hagyma, paprika, paradicsom, burgonya, fokhagyma, kömény, majoranna',
                'instructions': 'A húst kockákra vágjuk és enyhén megsózzuk. Megdinszteljük a hagymát, hozzáadjuk a paprikát. Felöntjük vízzel és főzzük 1.5 órát. Hozzáadjuk a burgonyát és tovább főzzük.',
                'images': 'https://images.unsplash.com/photo-1547592180-85f173990554?w=400&h=300&fit=crop',
                'HSI': 75.0, 'ESI': 60.0, 'PPI': 90.0, 'composite_score': 71.0
            },
            {
                'recipeid': 2,
                'title': 'Rántott Schnitzel Burgonyával',
                'ingredients': 'sertéshús, liszt, tojás, zsemlemorzsa, burgonya, olaj, só, bors',
                'instructions': 'A húst kikalapáljuk és megsózzuk. Lisztbe, majd felvert tojásba, végül zsemlemorzsába forgatjuk. Forró olajban mindkét oldalán kisütjük. A burgonyát héjában megfőzzük.',
                'images': 'https://images.unsplash.com/photo-1558030006-450675393462?w=400&h=300&fit=crop',
                'HSI': 55.0, 'ESI': 45.0, 'PPI': 85.0, 'composite_score': 57.0
            },
            {
                'recipeid': 3,
                'title': 'Vegetáriánus Lecsó',
                'ingredients': 'paprika, paradicsom, hagyma, tojás, tofu, olívaolaj, só, bors, fokhagyma',
                'instructions': 'A hagymát és fokhagymát megdinszteljük olívaolajban. Hozzáadjuk a felszeletelt paprikát. Paradicsomot és kockára vágott tofut adunk hozzá. Tojással dúsítjuk.',
                'images': 'https://images.unsplash.com/photo-1565299624946-b28f40a0ca4b?w=400&h=300&fit=crop',
                'HSI': 85.0, 'ESI': 80.0, 'PPI': 70.0, 'composite_score': 78.0
            },
            {
                'recipeid': 4,
                'title': 'Halászlé Szegedi Módra',
                'ingredients': 'ponty, csuka, harcsa, hagyma, paradicsom, paprika, só, babérlevél',
                'instructions': 'A halakat megtisztítjuk és feldaraboljuk. A halak fejéből és farkából erős alapot főzünk. Az alapot leszűrjük és beletesszük a haldarabokat. Paprikával ízesítjük.',
                'images': 'https://images.unsplash.com/photo-1544943910-4c1dc44aab44?w=400&h=300&fit=crop',
                'HSI': 80.0, 'ESI': 70.0, 'PPI': 75.0, 'composite_score': 74.0
            },
            {
                'recipeid': 5,
                'title': 'Töltött Káposzta',
                'ingredients': 'savanyú káposzta, darált hús, rizs, hagyma, paprika, kolbász, tejföl',
                'instructions': 'A káposztaleveleket leforrázuk és húsos rizzsel megtöltjük. Rétegesen főzzük kolbászdarabokkal és tejföllel tálaljuk.',
                'images': 'https://images.unsplash.com/photo-1574484284002-952d92456975?w=400&h=300&fit=crop',
                'HSI': 70.0, 'ESI': 55.0, 'PPI': 88.0, 'composite_score': 67.6
            },
            {
                'recipeid': 6,
                'title': 'Túrós Csusza',
                'ingredients': 'széles metélt, túró, tejföl, szalonna, hagyma, só, bors',
                'instructions': 'A tésztát sós vízben megfőzzük és leszűrjük. A szalonnát kockákra vágjuk és kisütjük. A tésztát összekeverjük a túróval, tejföllel és a szalonnával.',
                'images': 'https://images.unsplash.com/photo-1551698618-1dfe5d97d256?w=400&h=300&fit=crop',
                'HSI': 65.0, 'ESI': 55.0, 'PPI': 80.0, 'composite_score': 65.0
            },
            {
                'recipeid': 7,
                'title': 'Gombapaprikás Galuskával',
                'ingredients': 'gomba, hagyma, paprika, tejföl, liszt, tojás, petrezselyem, olaj',
                'instructions': 'A gombát felszeleteljük és kisütjük. Hagymát dinsztelünk, paprikát adunk hozzá. A gombát hozzáadjuk, tejföllel lefuttatjuk. Galuskát főzünk mellé.',
                'images': 'https://images.unsplash.com/photo-1565299507177-b0ac66763828?w=400&h=300&fit=crop',
                'HSI': 70.0, 'ESI': 75.0, 'PPI': 65.0, 'composite_score': 70.0
            },
            {
                'recipeid': 8,
                'title': 'Rákóczi Túrós',
                'ingredients': 'túró, tojás, cukor, tejföl, mazsola, citromhéj, vaníliapor',
                'instructions': 'A túrót átnyomjuk szitán és összekeverjük a tojásokkal. Cukrot, mazsolát és citromhéjat adunk hozzá. Sütőformában megsütjük. Tejfölös krémmel tálaljuk.',
                'images': 'https://images.unsplash.com/photo-1571877227200-a0d98ea607e9?w=400&h=300&fit=crop',
                'HSI': 60.0, 'ESI': 65.0, 'PPI': 85.0, 'composite_score': 68.0
            },
            {
                'recipeid': 9,
                'title': 'Zöldséges Ratatouille',
                'ingredients': 'cukkini, padlizsán, paprika, paradicsom, hagyma, fokhagyma, olívaolaj, bazsalikom',
                'instructions': 'Az összes zöldséget kockákra vágjuk. A hagymát és fokhagymát megpirítjuk. Rétegesen hozzáadjuk a zöldségeket. Bazsalikommal és fűszerekkel ízesítjük.',
                'images': 'https://images.unsplash.com/photo-1572441713132-51c75654db73?w=400&h=300&fit=crop',
                'HSI': 90.0, 'ESI': 85.0, 'PPI': 60.0, 'composite_score': 79.0
            },
            {
                'recipeid': 10,
                'title': 'Hortobágyi Palacsinta',
                'ingredients': 'palacsinta, csirkehús, gomba, hagyma, paprika, tejföl, sajt',
                'instructions': 'Palacsintát sütünk. A csirkehúst megpároljuk gombával és hagymával. A palacsintákat megtöltjük és feltekerjük. Tejfölös mártással sütőben átmelegítjük.',
                'images': 'https://images.unsplash.com/photo-1593560708920-61dd2833c471?w=400&h=300&fit=crop',
                'HSI': 70.0, 'ESI': 60.0, 'PPI': 80.0, 'composite_score': 68.0
            }
        ]
        
        df = pd.DataFrame(sample_recipes)
        df.to_csv(output_path, index=False, encoding='utf-8')
        
        print(f"✅ Sample CSV létrehozva: {len(df)} recept")
        print(f"🖼️ Külső képek Unsplash-ből")
        
        return output_path

class EnhancedRecipeRecommender:
    """Recept ajánló rendszer - JAVÍTOTT"""
    
    def __init__(self):
        # CSV létrehozása/ellenőrzése
        self.csv_path = CSVProcessor.create_processed_csv()
        self.recipes_df = self.load_recipes()
        
        print(f"🍽️ Recept rendszer inicializálva: {len(self.recipes_df) if self.recipes_df is not None else 0} recept")
    
    def load_recipes(self):
        """Receptek betöltése CSV-ből"""
        try:
            if not self.csv_path.exists():
                print(f"❌ CSV nem található: {self.csv_path}")
                return None
            
            df = pd.read_csv(self.csv_path)
            print(f"✅ CSV betöltve: {len(df)} recept")
            
            # Kötelező oszlopok ellenőrzése
            required_cols = ['recipeid', 'title', 'ingredients', 'images', 'HSI', 'ESI', 'PPI']
            missing_cols = [col for col in required_cols if col not in df.columns]
            
            if missing_cols:
                print(f"⚠️ Hiányzó oszlopok: {missing_cols}")
                return None
            
            # Debug: képek ellenőrzése
            print(f"🖼️ Képek ellenőrzése:")
            for i in range(min(3, len(df))):
                recipe = df.iloc[i]
                print(f"   {recipe['title']}: {recipe['images']}")
            
            return df
            
        except Exception as e:
            print(f"❌ CSV betöltési hiba: {e}")
            return None
    
    def get_recommendations(self, version='v1', n_recommendations=5):
        """Ajánlások lekérése"""
        if self.recipes_df is None or len(self.recipes_df) == 0:
            print("❌ Nincs recept adat!")
            return []
        
        # Sample kiválasztás
        sample_size = min(n_recommendations, len(self.recipes_df))
        recommendations = self.recipes_df.sample(n=sample_size).to_dict('records')
        
        # Magyarázatok hozzáadása
        for rec in recommendations:
            if version in ['v2', 'v3']:
                rec['explanation'] = self.generate_explanation(rec, version)
        
        print(f"✅ {len(recommendations)} ajánlás generálva ({version})")
        
        # Debug: ajánlások ellenőrzése
        print("🔍 Ajánlás debug:")
        for i, rec in enumerate(recommendations):
            print(f"   {i+1}. {rec['title']} - Kép: {rec.get('images', 'NINCS')[:60]}...")
        
        return recommendations
    
    def generate_explanation(self, recipe, version):
        """Magyarázat generálása"""
        explanations = []
        
        if recipe['HSI'] > 70:
            explanations.append("💚 Magas tápérték és egészséges összetevők")
        if recipe['ESI'] > 70:
            explanations.append("🌱 Környezetbarát ingrediensek")
        if recipe['PPI'] > 80:
            explanations.append("⭐ Népszerű és kipróbált recept")
        
        if not explanations:
            explanations.append("🍽️ Kiegyensúlyozott összetétel")
        
        if version == 'v3':
            detailed = f"Ez a recept {recipe['composite_score']:.0f}/100 pontot ért el összesített értékelésünkben. "
            detailed += " • ".join(explanations)
            return detailed
        else:
            return " • ".join(explanations)

# Global objektumok
db = UserStudyDatabase()
recommender = EnhancedRecipeRecommender()

def get_user_version():
    if 'version' not in session:
        versions = ['v1', 'v2', 'v3']
        session['version'] = random.choice(versions)
    return session['version']

# ROUTES

@user_study_bp.route('/')
def welcome():
    return render_template('welcome.html')

@user_study_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        try:
            age_group = request.form.get('age_group')
            education = request.form.get('education')
            cooking_frequency = request.form.get('cooking_frequency')
            sustainability_awareness = int(request.form.get('sustainability_awareness', 3))
            
            version = get_user_version()
            user_id = db.create_user(age_group, education, cooking_frequency, 
                                   sustainability_awareness, version)
            
            session['user_id'] = user_id
            session['version'] = version
            
            return redirect(url_for('user_study.instructions'))
            
        except Exception as e:
            print(f"Registration error: {e}")
            return render_template('register.html', error='Regisztráció sikertelen')
    
    return render_template('register.html')

@user_study_bp.route('/instructions')
def instructions():
    if 'user_id' not in session:
        return redirect(url_for('user_study.register'))
    
    version = session.get('version', 'v1')
    return render_template('instructions.html', version=version)

@user_study_bp.route('/study')
def study():
    """Fő tanulmány oldal - KÉPEKKEL ÉS CSV ADATOKKAL"""
    if 'user_id' not in session:
        return redirect(url_for('user_study.register'))
    
    version = session.get('version', 'v1')
    
    # Ajánlások lekérése
    recommendations = recommender.get_recommendations(version=version, n_recommendations=5)
    
    if not recommendations:
        return "❌ Hiba: Nem sikerült betölteni a recepteket. Ellenőrizd a CSV fájlokat.", 500
    
    print(f"🔍 Template-nek átadott {len(recommendations)} ajánlás ({version})")
    
    return render_template('study.html', 
                         recommendations=recommendations, 
                         version=version)

@user_study_bp.route('/rate_recipe', methods=['POST'])
def rate_recipe():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    user_id = session['user_id']
    data = request.get_json()
    
    recipe_id = int(data.get('recipe_id'))
    rating = int(data.get('rating'))
    explanation_helpful = data.get('explanation_helpful')
    view_time = data.get('view_time_seconds', 0)
    interaction_order = data.get('interaction_order', 0)
    
    db.log_interaction(user_id, recipe_id, rating, explanation_helpful, view_time, interaction_order)
    
    return jsonify({'status': 'success'})

@user_study_bp.route('/questionnaire', methods=['GET', 'POST'])
def questionnaire():
    if 'user_id' not in session:
        return redirect(url_for('user_study.register'))
    
    if request.method == 'POST':
        user_id = session['user_id']
        
        responses = {
            'system_usability': request.form.get('system_usability'),
            'recommendation_quality': request.form.get('recommendation_quality'),
            'trust_level': request.form.get('trust_level'),
            'explanation_clarity': request.form.get('explanation_clarity'),
            'sustainability_importance': request.form.get('sustainability_importance'),
            'overall_satisfaction': request.form.get('overall_satisfaction'),
            'additional_comments': request.form.get('additional_comments', '')
        }
        
        db.save_questionnaire(user_id, responses)
        return redirect(url_for('user_study.thank_you'))
    
    version = session.get('version', 'v1')
    return render_template('questionnaire.html', version=version)

@user_study_bp.route('/thank_you')
def thank_you():
    version = session.get('version', 'v1')
    return render_template('thank_you.html', version=version)

@user_study_bp.route('/admin/stats')
def admin_stats():
    """Admin statisztikák"""
    try:
        conn = db.get_connection()
        
        stats = {}
        
        # Alapstatisztikák
        result = conn.execute('SELECT COUNT(*) as count FROM participants').fetchone()
        stats['total_participants'] = result['count'] if result else 0
        
        result = conn.execute('SELECT COUNT(*) as count FROM participants WHERE is_completed = 1').fetchone()
        stats['completed_participants'] = result['count'] if result else 0
        
        if stats['total_participants'] > 0:
            stats['completion_rate'] = stats['completed_participants'] / stats['total_participants']
        else:
            stats['completion_rate'] = 0
        
        # Verzió eloszlás
        version_results = conn.execute('''
            SELECT version, 
                   COUNT(*) as count,
                   SUM(CASE WHEN is_completed = 1 THEN 1 ELSE 0 END) as completed
            FROM participants 
            GROUP BY version
        ''').fetchall()
        
        stats['version_distribution'] = [dict(row) for row in version_results]
        
        # Átlagos értékelések
        rating_results = conn.execute('''
            SELECT p.version, AVG(i.rating) as avg_rating, COUNT(i.rating) as count
            FROM participants p
            JOIN interactions i ON p.user_id = i.user_id
            WHERE i.rating IS NOT NULL
            GROUP BY p.version
        ''').fetchall()
        
        stats['average_ratings'] = [dict(row) for row in rating_results]
        
        # Kérdőív eredmények
        questionnaire_results = conn.execute('''
            SELECT p.version,
                   AVG(q.system_usability) as avg_usability,
                   AVG(q.recommendation_quality) as avg_quality,
                   AVG(q.trust_level) as avg_trust,
                   AVG(q.explanation_clarity) as avg_clarity,
                   AVG(q.overall_satisfaction) as avg_satisfaction
            FROM participants p
            JOIN questionnaire q ON p.user_id = q.user_id
            GROUP BY p.version
        ''').fetchall()
        
        stats['questionnaire_results'] = [dict(row) for row in questionnaire_results]
        
        # Átlagos interakciók
        interactions_count = conn.execute('SELECT COUNT(*) as count FROM interactions').fetchone()
        if stats['total_participants'] > 0:
            stats['avg_interactions_per_user'] = interactions_count['count'] / stats['total_participants']
        else:
            stats['avg_interactions_per_user'] = 0
        
        conn.close()
        
        return render_template('admin_stats.html', stats=stats)
        
    except Exception as e:
        return f"Stats error: {e}", 500

# DEBUG route CSV ellenőrzéshez
@user_study_bp.route('/debug/csv')
def debug_csv():
    """CSV debug információk"""
    try:
        result = "<h2>🔍 CSV Debug Information</h2>"
        
        # Processed CSV ellenőrzés
        csv_path = project_root / "data" / "processed_recipes.csv"
        result += f"<h3>📊 Processed CSV Status:</h3>"
        result += f"Path: {csv_path}<br>"
        result += f"Exists: {'✅ YES' if csv_path.exists() else '❌ NO'}<br>"
        
        if csv_path.exists():
            try:
                df = pd.read_csv(csv_path)
                result += f"Rows: {len(df)}<br>"
                result += f"Columns: {list(df.columns)}<br><br>"
                
                result += "<h3>🖼️ Image URLs (first 3):</h3>"
                for i in range(min(3, len(df))):
                    recipe = df.iloc[i]
                    result += f"<b>{recipe['title']}:</b><br>"
                    result += f"Image: {recipe.get('images', 'NINCS')}<br><br>"
                
            except Exception as e:
                result += f"CSV read error: {e}<br>"

      # Add this debug route to user_study.py

@user_study_bp.route('/debug/esi_zero')
def debug_esi_zero():
    """Debug ESI=0 values"""
    try:
        result = "<h2>🔍 ESI=0 Debug Analysis</h2>"
        
        # Load processed CSV
        csv_path = project_root / "data" / "processed_recipes.csv"
        if not csv_path.exists():
            return "❌ processed_recipes.csv not found"
        
        df = pd.read_csv(csv_path)
        result += f"<h3>📊 CSV Statistics:</h3>"
        result += f"Total recipes: {len(df)}<br>"
        
        # Check score columns
        score_cols = ['ESI', 'HSI', 'PPI', 'composite_score']
        for col in score_cols:
            if col in df.columns:
                min_val = df[col].min()
                max_val = df[col].max()
                mean_val = df[col].mean()
                zero_count = (df[col] == 0).sum()
                
                result += f"<b>{col}:</b> {min_val:.2f} - {max_val:.2f} (avg: {mean_val:.2f}, zeros: {zero_count})<br>"
        
        # Check raw scores if available
        result += f"<h3>🌱 Raw Environmental Scores:</h3>"
        if 'env_score_raw' in df.columns:
            env_min = df['env_score_raw'].min()
            env_max = df['env_score_raw'].max()
            env_mean = df['env_score_raw'].mean()
            
            result += f"env_score_raw range: {env_min:.2f} - {env_max:.2f} (avg: {env_mean:.2f})<br>"
            
            # Show normalization calculation
            result += f"<h4>Normalization Formula:</h4>"
            result += f"ESI = 100 - ((env_score_raw - {env_min:.2f}) / ({env_max:.2f} - {env_min:.2f}) * 100)<br><br>"
            
            # Show examples
            result += f"<h4>Normalization Examples:</h4>"
            sample_recipes = df.head(5)
            for _, recipe in sample_recipes.iterrows():
                raw_env = recipe['env_score_raw']
                esi = recipe['ESI']
                
                if env_max > env_min:
                    calculated_esi = 100 - ((raw_env - env_min) / (env_max - env_min) * 100)
                else:
                    calculated_esi = 70.0
                
                result += f"<b>{recipe['title'][:40]}...</b><br>"
                result += f"   Raw env_score: {raw_env:.2f}<br>"
                result += f"   Stored ESI: {esi:.2f}<br>"
                result += f"   Calculated ESI: {calculated_esi:.2f}<br>"
                result += f"   Match: {'✅' if abs(esi - calculated_esi) < 0.01 else '❌'}<br><br>"
        
        # Find recipes with ESI=0
        zero_esi_recipes = df[df['ESI'] == 0]
        if len(zero_esi_recipes) > 0:
            result += f"<h3>❌ Recipes with ESI=0 ({len(zero_esi_recipes)} found):</h3>"
            for _, recipe in zero_esi_recipes.head(10).iterrows():
                result += f"<b>{recipe['title']}:</b><br>"
                result += f"   ESI: {recipe['ESI']:.2f}<br>"
                result += f"   HSI: {recipe['HSI']:.2f}<br>"
                result += f"   PPI: {recipe['PPI']:.2f}<br>"
                if 'env_score_raw' in df.columns:
                    result += f"   Raw env_score: {recipe['env_score_raw']:.2f}<br>"
                result += f"<br>"
        else:
            result += f"<h3>✅ No recipes with ESI=0 found</h3>"
        
        # Composite score verification
        result += f"<h3>🔢 Composite Score Verification:</h3>"
        sample = df.sample(n=3)
        for _, recipe in sample.iterrows():
            stored_composite = recipe['composite_score']
            calculated_composite = recipe['ESI'] * 0.4 + recipe['HSI'] * 0.4 + recipe['PPI'] * 0.2
            
            result += f"<b>{recipe['title'][:40]}...</b><br>"
            result += f"   ESI: {recipe['ESI']:.1f}, HSI: {recipe['HSI']:.1f}, PPI: {recipe['PPI']:.1f}<br>"
            result += f"   Stored composite: {stored_composite:.2f}<br>"
            result += f"   Calculated composite: {calculated_composite:.2f}<br>"
            result += f"   Match: {'✅' if abs(stored_composite - calculated_composite) < 0.01 else '❌'}<br><br>"
        
        return result
        
    except Exception as e:
        return f"Debug error: {e}"
        
        # Original CSV ellenőrzés
        original_csv = project_root / "hungarian_recipes_github.csv"
        result += f"<h3>📋 Original CSV Status:</h3>"
        result += f"Path: {original_csv}<br>"
        result += f"Exists: {'✅ YES' if original_csv.exists() else '❌ NO'}<br>"
        
        if original_csv.exists():
            try:
                df_orig = pd.read_csv(original_csv)
                result += f"Rows: {len(df_orig)}<br>"
                result += f"Columns: {list(df_orig.columns)}<br>"
            except Exception as e:
                result += f"Original CSV read error: {e}<br>"
        
        # Recommender status
        result += f"<h3>🤖 Recommender Status:</h3>"
        result += f"Recipes loaded: {len(recommender.recipes_df) if recommender.recipes_df is not None else 0}<br>"
        
        # Test recommendation
        try:
            test_recs = recommender.get_recommendations('v1', 2)
            result += f"Test recommendations: {len(test_recs)}<br>"
            if test_recs:
                result += f"First recipe: {test_recs[0]['title']}<br>"
                result += f"First image: {test_recs[0].get('images', 'NINCS')}<br>"
        except Exception as e:
            result += f"Test recommendation error: {e}<br>"
        
        return result
        
    except Exception as e:
        return f"Debug error: {e}"

# Export
__all__ = ['user_study_bp']
