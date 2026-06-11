import yfinance as yf
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report
import joblib
import warnings
warnings.filterwarnings('ignore')

def build_ml_filter():
    print("[*] INITIATING MACHINE LEARNING VOLUME FILTER CONSTRUCTION")
    print("[*] Downloading 60 Days of High-Resolution NAS100 Data...")
    
    # Download 5m data
    df = yf.download("NQ=F", period="60d", interval="5m", progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.droplevel(1)
        
    print("[*] Engineering Institutional Volume Features...")
    
    # Core EMAs
    df['EMA_50'] = df['Close'].ewm(span=50, adjust=False).mean()
    df['EMA_200'] = df['Close'].ewm(span=200, adjust=False).mean()
    
    # Volume Velocity Features
    df['Vol_SMA_20'] = df['Volume'].rolling(window=20).mean()
    df['Vol_Spike_Ratio'] = df['Volume'] / df['Vol_SMA_20']
    
    # Price Momentum Features
    df['Price_ROC_5'] = df['Close'].pct_change(periods=5)
    df['Distance_From_200'] = (df['Close'] - df['EMA_200']) / df['EMA_200']
    
    # Target Variable Creation (Simulating Breakout Success)
    # If the price goes up by at least 0.15% in the next 10 candles, it's a successful long breakout.
    # We will just train a general "Trend Continuation" target for simplicity.
    df['Future_Return_10'] = df['Close'].shift(-10) / df['Close'] - 1
    
    # 1 if it's a strong continuation (>0.1%), 0 if it fails/chops
    df['Target'] = np.where(df['Future_Return_10'] > 0.001, 1, 0)
    
    # Drop NaNs
    df.dropna(inplace=True)
    
    features = ['Vol_Spike_Ratio', 'Price_ROC_5', 'Distance_From_200']
    X = df[features]
    y = df['Target']
    
    print("[*] Splitting Data Matrix (80% Train / 20% Test)...")
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    print("[*] Training Random Forest Classifier (100 Estimators)...")
    model = RandomForestClassifier(n_estimators=100, max_depth=5, random_state=42)
    model.fit(X_train, y_train)
    
    y_pred = model.predict(X_test)
    acc = accuracy_score(y_test, y_pred)
    
    print(f"\n[+] AI Model Trained Successfully. Accuracy: {acc*100:.2f}%")
    print("\nClassification Report (Fakeout vs Real Breakout):")
    print(classification_report(y_test, y_pred))
    
    # Save the model
    joblib.dump(model, 'kessler_volume_model.pkl')
    print("[!] Model saved as 'kessler_volume_model.pkl'. Kessler Engine can now ingest this.")

if __name__ == "__main__":
    build_ml_filter()
