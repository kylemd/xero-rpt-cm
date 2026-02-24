"""
Flask server for the Xero Report Code Mapping web interface
"""

import os
import json
import tempfile
import pathlib
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from werkzeug.utils import secure_filename

# Import our modules
import sys
sys.path.append(str(pathlib.Path(__file__).parent.parent))

from file_handler import load_chart_file, load_trial_balance_file
from integrity_validator import IntegrityValidator
from mapping_logic_v15 import main as run_mapping_logic
import argparse

app = Flask(__name__)
CORS(app)

# Configuration
UPLOAD_FOLDER = tempfile.gettempdir()
ALLOWED_EXTENSIONS = {'csv', 'xlsx'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Initialize validator
project_root = pathlib.Path(__file__).parent.parent
validator = IntegrityValidator(project_root)


def allowed_file(filename):
    """Check if file extension is allowed."""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def save_uploaded_file(file, prefix):
    """Save uploaded file to temporary directory."""
    if file and allowed_file(file.filename):
        filename = secure_filename(f"{prefix}_{file.filename}")
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        return filepath
    return None


@app.route('/')
def index():
    """Serve the main HTML page."""
    return send_from_directory('.', 'index.html')


@app.route('/<path:filename>')
def static_files(filename):
    """Serve static files (CSS, JS)."""
    return send_from_directory('.', filename)


@app.route('/health')
def health_check():
    """Health check endpoint."""
    return jsonify({
        'status': 'healthy',
        'message': 'Server is running',
        'validator_loaded': validator is not None
    })


@app.route('/validate', methods=['POST'])
def validate_files():
    """Validate uploaded files for integrity issues and balance anomalies."""
    chart_path = None
    trial_path = None
    
    try:
        # Get uploaded files
        chart_file = request.files.get('chart_file')
        trial_file = request.files.get('trial_file')
        template = request.form.get('template')
        industry = request.form.get('industry', '')
        
        print(f"Received files: chart={chart_file.filename if chart_file else None}, trial={trial_file.filename if trial_file else None}")
        print(f"Template: {template}, Industry: {industry}")
        
        if not chart_file or not trial_file or not template:
            return jsonify({'error': 'Missing required files or template'}), 400
        
        # Save files temporarily
        chart_path = save_uploaded_file(chart_file, 'chart')
        trial_path = save_uploaded_file(trial_file, 'trial')
        
        if not chart_path or not trial_path:
            return jsonify({'error': 'Invalid file format'}), 400
        
        print(f"Saved files: chart={chart_path}, trial={trial_path}")
        
        # Load and validate files
        chart_df = load_chart_file(pathlib.Path(chart_path))
        trial_df, trial_metadata = load_trial_balance_file(pathlib.Path(trial_path))
        
        print(f"Loaded chart with {len(chart_df)} rows, trial with {len(trial_df)} rows")
        print(f"Trial metadata: {trial_metadata}")
        
        # Run integrity validation
        integrity_findings = validator.validate_chart_dataframe(chart_df, chart_file.filename)
        print(f"Found {len(integrity_findings)} integrity findings")
        
        # Detect balance anomalies
        balance_anomalies = []
        account_code_col = None
        for col in trial_df.columns:
            if 'code' in col.lower() and '*' not in col.lower():
                account_code_col = col
                break
        
        print(f"Account code column: {account_code_col}")
        
        if account_code_col:
            period_cols = [col for col in trial_df.columns 
                          if col not in [account_code_col, 'Account', 'Account Type', 
                                       'Debit - Year to date', 'Credit - Year to date']]
            
            print(f"Period columns: {period_cols}")
            
            for _, row in trial_df.iterrows():
                account_code = str(row.get(account_code_col, '')).strip()
                account_type = str(row.get('Account Type', '')).strip()
                
                if account_code and account_type and account_code != 'nan' and account_type != 'nan':
                    period_balances = {}
                    for col in period_cols:
                        balance = row.get(col, 0)
                        if pd.notna(balance):
                            try:
                                period_balances[col] = float(balance)
                            except (ValueError, TypeError):
                                period_balances[col] = 0.0
                    
                    if len(period_balances) >= 2:
                        anomaly = validator.detect_balance_anomalies(account_code, account_type, period_balances)
                        if anomaly['is_anomaly']:
                            balance_anomalies.append({
                                'account_code': account_code,
                                'account_type': account_type,
                                'severity': anomaly['severity'],
                                'recommendation': anomaly['recommendation'],
                                'periods_checked': anomaly['periods_checked']
                            })
        
        print(f"Found {len(balance_anomalies)} balance anomalies")
        
        # Clean up temporary files
        if chart_path and os.path.exists(chart_path):
            os.unlink(chart_path)
        if trial_path and os.path.exists(trial_path):
            os.unlink(trial_path)
        
        return jsonify({
            'integrity_findings': integrity_findings,
            'balance_anomalies': balance_anomalies,
            'trial_metadata': trial_metadata,
            'summary': {
                'total_issues': len(integrity_findings) + len(balance_anomalies),
                'integrity_violations': len(integrity_findings),
                'balance_anomalies': len(balance_anomalies)
            }
        })
        
    except Exception as e:
        print(f"Error in validate_files: {str(e)}")
        import traceback
        traceback.print_exc()
        
        # Clean up temporary files on error
        if chart_path and os.path.exists(chart_path):
            try:
                os.unlink(chart_path)
            except:
                pass
        if trial_path and os.path.exists(trial_path):
            try:
                os.unlink(trial_path)
            except:
                pass
        
        return jsonify({'error': f'Validation failed: {str(e)}'}), 500


@app.route('/process', methods=['POST'])
def process_files():
    """Process files with the mapping logic."""
    try:
        # Get uploaded files and parameters
        chart_file = request.files.get('chart_file')
        trial_file = request.files.get('trial_file')
        template = request.form.get('template')
        industry = request.form.get('industry', '')
        decisions_json = request.form.get('decisions', '[]')
        
        if not chart_file or not trial_file or not template:
            return jsonify({'error': 'Missing required files or template'}), 400
        
        # Save files temporarily
        chart_path = save_uploaded_file(chart_file, 'chart')
        trial_path = save_uploaded_file(trial_file, 'trial')
        
        if not chart_path or not trial_path:
            return jsonify({'error': 'Invalid file format'}), 400
        
        # Parse resolution decisions
        decisions = json.loads(decisions_json)
        
        # Create temporary output directory
        output_dir = tempfile.mkdtemp()
        
        # Run mapping logic
        args = argparse.Namespace(
            client_chart=chart_path,
            client_trialbalance=trial_path,
            chart_template_name=template,
            industry=industry,
            validate_only=False
        )
        
        # Change to output directory for file generation
        original_cwd = os.getcwd()
        os.chdir(output_dir)
        
        try:
            run_mapping_logic(args)
        finally:
            os.chdir(original_cwd)
        
        # Find generated files
        output_files = []
        for file in os.listdir(output_dir):
            if file.endswith('.csv') or file.endswith('.json'):
                output_files.append(file)
        
        # Clean up temporary files
        os.unlink(chart_path)
        os.unlink(trial_path)
        
        return jsonify({
            'success': True,
            'output_file': output_files[0] if output_files else 'AugmentedChartOfAccounts.csv',
            'output_directory': output_dir,
            'accounts_processed': 'N/A',  # Would need to parse from output
            'mappings_applied': 'N/A',
            'integrity_resolved': len([d for d in decisions if d.get('type') == 'integrity']),
            'balance_addressed': len([d for d in decisions if d.get('type') == 'balance']),
            'manual_reviews': 0
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/allowed-codes/<account_type>')
def get_allowed_codes(account_type):
    """Get allowed reporting codes for a given account type."""
    try:
        allowed_codes = validator.get_allowed_codes_for_type(account_type)
        return jsonify({
            'account_type': account_type,
            'allowed_codes': list(allowed_codes)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/balance-history/<account_code>')
def get_balance_history(account_code):
    """Get balance history for a specific account."""
    try:
        # This would need to be implemented based on the trial balance data
        # For now, return mock data
        return jsonify({
            'account_code': account_code,
            'balance_history': [
                {'period': '30 June 2024', 'balance': 1000.00},
                {'period': '30 June 2023', 'balance': 950.00},
                {'period': '30 June 2022', 'balance': 900.00}
            ]
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/export-decisions', methods=['POST'])
def export_decisions():
    """Export resolution decisions for retraining."""
    try:
        decisions = request.json.get('decisions', [])
        metadata = request.json.get('metadata', {})
        
        # Create resolution history directory
        resolution_dir = project_root / 'resolution_history'
        resolution_dir.mkdir(exist_ok=True)
        
        # Create timestamped directory
        timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        client_name = metadata.get('chart_file', 'Unknown').split('.')[0]
        session_dir = resolution_dir / f"{timestamp}_{client_name}"
        session_dir.mkdir(exist_ok=True)
        
        # Save decisions
        decisions_file = session_dir / 'decisions.json'
        with open(decisions_file, 'w', encoding='utf-8') as f:
            json.dump(decisions, f, indent=2)
        
        # Save metadata
        metadata_file = session_dir / 'metadata.json'
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2)
        
        return jsonify({
            'success': True,
            'session_directory': str(session_dir),
            'decisions_saved': len(decisions)
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.errorhandler(413)
def too_large(e):
    """Handle file too large error."""
    return jsonify({'error': 'File too large. Maximum size is 16MB.'}), 413


@app.errorhandler(500)
def internal_error(e):
    """Handle internal server error."""
    return jsonify({'error': 'Internal server error. Please try again.'}), 500


if __name__ == '__main__':
    # Import pandas here to avoid import issues
    import pandas as pd
    
    print("Starting Xero Report Code Mapping web server...")
    print(f"Project root: {project_root}")
    print(f"Upload folder: {UPLOAD_FOLDER}")
    
    app.run(debug=True, host='0.0.0.0', port=5000)
