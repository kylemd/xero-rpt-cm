/**
 * Client-side JavaScript for the Xero Report Code Mapping interface
 */

class ReportCodeMapper {
    constructor() {
        this.chartFile = null;
        this.trialFile = null;
        this.validationResults = null;
        this.resolutionDecisions = [];
        
        this.initializeEventListeners();
    }
    
    initializeEventListeners() {
        // File upload handlers
        this.setupFileUpload('chart-file', 'chart-upload', 'chart-info');
        this.setupFileUpload('trial-file', 'trial-upload', 'trial-info');
        
        // Button handlers
        document.getElementById('validate-btn').addEventListener('click', () => this.validateFiles());
        document.getElementById('proceed-btn').addEventListener('click', () => this.proceedWithMapping());
        document.getElementById('resolve-btn').addEventListener('click', () => this.showResolutionInterface());
        document.getElementById('accept-all-btn').addEventListener('click', () => this.acceptAllSuggestions());
        document.getElementById('export-decisions-btn').addEventListener('click', () => this.exportDecisions());
        document.getElementById('bulk-reclassify-btn').addEventListener('click', () => this.bulkReclassify());
        
        // Tab handlers
        document.querySelectorAll('.tab-btn').forEach(btn => {
            btn.addEventListener('click', (e) => this.switchTab(e.target.dataset.tab));
        });
        
        // Form validation
        document.getElementById('template-select').addEventListener('change', () => this.updateValidateButton());
    }
    
    setupFileUpload(inputId, dropZoneId, infoId) {
        const input = document.getElementById(inputId);
        const dropZone = document.getElementById(dropZoneId);
        const info = document.getElementById(infoId);
        
        // Click to upload
        dropZone.addEventListener('click', () => input.click());
        
        // Drag and drop
        dropZone.addEventListener('dragover', (e) => {
            e.preventDefault();
            dropZone.classList.add('dragover');
        });
        
        dropZone.addEventListener('dragleave', () => {
            dropZone.classList.remove('dragover');
        });
        
        dropZone.addEventListener('drop', (e) => {
            e.preventDefault();
            dropZone.classList.remove('dragover');
            
            const files = e.dataTransfer.files;
            if (files.length > 0) {
                this.handleFileSelect(files[0], inputId, infoId);
            }
        });
        
        // File input change
        input.addEventListener('change', (e) => {
            if (e.target.files.length > 0) {
                this.handleFileSelect(e.target.files[0], inputId, infoId);
            }
        });
    }
    
    handleFileSelect(file, inputId, infoId) {
        const info = document.getElementById(infoId);
        const fileName = info.querySelector('.file-name');
        const fileStatus = info.querySelector('.file-status');
        
        // Validate file type
        const allowedTypes = ['.csv', '.xlsx'];
        const fileExt = file.name.toLowerCase().substring(file.name.lastIndexOf('.'));
        
        if (!allowedTypes.includes(fileExt)) {
            fileStatus.textContent = 'Invalid file type. Please upload CSV or XLSX.';
            fileStatus.className = 'file-status error';
            info.style.display = 'block';
            return;
        }
        
        // Store file reference
        if (inputId === 'chart-file') {
            this.chartFile = file;
        } else if (inputId === 'trial-file') {
            this.trialFile = file;
        }
        
        // Update UI
        fileName.textContent = file.name;
        fileStatus.textContent = 'File ready';
        fileStatus.className = 'file-status';
        info.style.display = 'block';
        
        // Add remove button
        this.addRemoveButton(infoId);
        
        this.updateValidateButton();
    }
    
    addRemoveButton(infoId) {
        const info = document.getElementById(infoId);
        const existingRemoveBtn = info.querySelector('.remove-file-btn');
        
        if (existingRemoveBtn) {
            existingRemoveBtn.remove();
        }
        
        const removeBtn = document.createElement('button');
        removeBtn.type = 'button';
        removeBtn.className = 'btn btn-danger btn-sm remove-file-btn';
        removeBtn.textContent = 'Remove';
        removeBtn.style.marginTop = '10px';
        removeBtn.onclick = () => this.removeFile(infoId);
        
        info.appendChild(removeBtn);
    }
    
    removeFile(infoId) {
        const info = document.getElementById(infoId);
        const input = document.getElementById(infoId.replace('-info', '-file'));
        
        // Clear file reference
        if (infoId === 'chart-info') {
            this.chartFile = null;
        } else if (infoId === 'trial-info') {
            this.trialFile = null;
        }
        
        // Clear input
        input.value = '';
        
        // Hide info
        info.style.display = 'none';
        
        // Remove remove button
        const removeBtn = info.querySelector('.remove-file-btn');
        if (removeBtn) {
            removeBtn.remove();
        }
        
        this.updateValidateButton();
    }
    
    updateValidateButton() {
        const validateBtn = document.getElementById('validate-btn');
        const template = document.getElementById('template-select').value;
        
        const canValidate = this.chartFile && this.trialFile && template;
        validateBtn.disabled = !canValidate;
    }
    
    async validateFiles() {
        if (!this.chartFile || !this.trialFile) {
            this.showError('Please upload both Chart of Accounts and Trial Balance files.');
            return;
        }
        
        const template = document.getElementById('template-select').value;
        if (!template) {
            this.showError('Please select a template chart.');
            return;
        }
        
        this.showProcessing('Validating files...');
        
        try {
            const formData = new FormData();
            formData.append('chart_file', this.chartFile);
            formData.append('trial_file', this.trialFile);
            formData.append('template', template);
            formData.append('industry', document.getElementById('industry-input').value);
            
            const response = await fetch('/validate', {
                method: 'POST',
                body: formData
            });
            
            if (!response.ok) {
                throw new Error(`Validation failed: ${response.statusText}`);
            }
            
            this.validationResults = await response.json();
            this.showValidationResults();
            
        } catch (error) {
            this.showError(`Validation failed: ${error.message}`);
        } finally {
            this.hideProcessing();
        }
    }
    
    showValidationResults() {
        const section = document.getElementById('validation-section');
        const summary = document.getElementById('validation-summary');
        const proceedBtn = document.getElementById('proceed-btn');
        const resolveBtn = document.getElementById('resolve-btn');
        
        // Build summary
        const integrityCount = this.validationResults.integrity_findings?.length || 0;
        const balanceCount = this.validationResults.balance_anomalies?.length || 0;
        const totalIssues = integrityCount + balanceCount;
        
        summary.innerHTML = `
            <div class="summary-card ${totalIssues === 0 ? 'success' : 'warning'}">
                <h3>${totalIssues}</h3>
                <p>Total Issues Found</p>
            </div>
            <div class="summary-card ${integrityCount === 0 ? 'success' : 'error'}">
                <h3>${integrityCount}</h3>
                <p>Integrity Violations</p>
            </div>
            <div class="summary-card ${balanceCount === 0 ? 'success' : 'warning'}">
                <h3>${balanceCount}</h3>
                <p>Balance Anomalies</p>
            </div>
        `;
        
        // Show appropriate buttons
        if (totalIssues === 0) {
            proceedBtn.style.display = 'inline-block';
            resolveBtn.style.display = 'none';
        } else {
            proceedBtn.style.display = 'none';
            resolveBtn.style.display = 'inline-block';
        }
        
        section.style.display = 'block';
    }
    
    showResolutionInterface() {
        const section = document.getElementById('resolution-section');
        section.style.display = 'block';
        
        this.populateIntegrityIssues();
        this.populateBalanceAnomalies();
    }
    
    populateIntegrityIssues() {
        const container = document.getElementById('integrity-issues');
        const issues = this.validationResults.integrity_findings || [];
        
        if (issues.length === 0) {
            container.innerHTML = '<p class="text-center">No integrity issues found.</p>';
            return;
        }
        
        container.innerHTML = issues.map(issue => `
            <div class="issue-item">
                <div class="issue-header">
                    <div class="issue-title">Account ${issue.account_code}: ${issue.type}</div>
                    <div class="issue-severity high">Integrity Violation</div>
                </div>
                <div class="issue-details">
                    <p><strong>Current Code:</strong> ${issue.reporting_code}</p>
                    <p><strong>Issue:</strong> ${issue.reason}</p>
                    <p><strong>Line:</strong> ${issue.line_number}</p>
                </div>
                <div class="issue-actions">
                    <select class="suggestion-select" data-issue-id="${issue.account_code}">
                        <option value="">Select suggested code...</option>
                        <!-- Suggestions will be populated by server -->
                    </select>
                    <button type="button" class="btn btn-success" onclick="mapper.acceptSuggestion('${issue.account_code}')">
                        Accept
                    </button>
                    <button type="button" class="btn btn-secondary" onclick="mapper.skipIssue('${issue.account_code}')">
                        Skip
                    </button>
                </div>
            </div>
        `).join('');
    }
    
    populateBalanceAnomalies() {
        const container = document.getElementById('balance-anomalies');
        const anomalies = this.validationResults.balance_anomalies || [];
        
        if (anomalies.length === 0) {
            container.innerHTML = '<p class="text-center">No balance anomalies found.</p>';
            return;
        }
        
        container.innerHTML = anomalies.map(anomaly => `
            <div class="issue-item">
                <div class="issue-header">
                    <div class="issue-title">Account ${anomaly.account_code}: ${anomaly.account_type}</div>
                    <div class="issue-severity ${anomaly.severity.toLowerCase()}">${anomaly.severity}</div>
                </div>
                <div class="issue-details">
                    <p><strong>Recommendation:</strong> ${anomaly.recommendation}</p>
                    <p><strong>Periods Checked:</strong> ${anomaly.periods_checked}</p>
                </div>
                <div class="balance-history">
                    <h4>Balance History</h4>
                    <table class="balance-table">
                        <thead>
                            <tr>
                                <th>Period</th>
                                <th>Balance</th>
                            </tr>
                        </thead>
                        <tbody>
                            <!-- Balance history will be populated by server -->
                        </tbody>
                    </table>
                </div>
                <div class="issue-actions">
                    <select class="suggestion-select" data-anomaly-id="${anomaly.account_code}">
                        <option value="">Select new type...</option>
                        <option value="Current Asset">Current Asset</option>
                        <option value="Current Liability">Current Liability</option>
                        <option value="Fixed Asset">Fixed Asset</option>
                        <option value="Non-current Liability">Non-current Liability</option>
                    </select>
                    <button type="button" class="btn btn-warning" onclick="mapper.reclassifyAccount('${anomaly.account_code}')">
                        Reclassify
                    </button>
                    <button type="button" class="btn btn-secondary" onclick="mapper.skipAnomaly('${anomaly.account_code}')">
                        Skip
                    </button>
                </div>
            </div>
        `).join('');
    }
    
    switchTab(tabName) {
        // Update tab buttons
        document.querySelectorAll('.tab-btn').forEach(btn => {
            btn.classList.remove('active');
        });
        document.querySelector(`[data-tab="${tabName}"]`).classList.add('active');
        
        // Update tab content
        document.querySelectorAll('.tab-content').forEach(content => {
            content.classList.remove('active');
        });
        document.getElementById(`${tabName}-tab`).classList.add('active');
    }
    
    acceptSuggestion(accountCode) {
        const select = document.querySelector(`[data-issue-id="${accountCode}"]`);
        const selectedCode = select.value;
        
        if (!selectedCode) {
            this.showError('Please select a suggested code.');
            return;
        }
        
        this.resolutionDecisions.push({
            type: 'integrity',
            account_code: accountCode,
            action: 'accept',
            new_code: selectedCode,
            timestamp: new Date().toISOString()
        });
        
        // Hide the issue
        const issueItem = select.closest('.issue-item');
        issueItem.style.opacity = '0.5';
        issueItem.style.pointerEvents = 'none';
        
        this.showSuccess(`Accepted suggestion for account ${accountCode}`);
    }
    
    skipIssue(accountCode) {
        this.resolutionDecisions.push({
            type: 'integrity',
            account_code: accountCode,
            action: 'skip',
            timestamp: new Date().toISOString()
        });
        
        // Hide the issue
        const issueItem = document.querySelector(`[data-issue-id="${accountCode}"]`).closest('.issue-item');
        issueItem.style.opacity = '0.5';
        issueItem.style.pointerEvents = 'none';
    }
    
    reclassifyAccount(accountCode) {
        const select = document.querySelector(`[data-anomaly-id="${accountCode}"]`);
        const newType = select.value;
        
        if (!newType) {
            this.showError('Please select a new account type.');
            return;
        }
        
        this.resolutionDecisions.push({
            type: 'balance',
            account_code: accountCode,
            action: 'reclassify',
            new_type: newType,
            timestamp: new Date().toISOString()
        });
        
        // Hide the anomaly
        const anomalyItem = select.closest('.issue-item');
        anomalyItem.style.opacity = '0.5';
        anomalyItem.style.pointerEvents = 'none';
        
        this.showSuccess(`Reclassified account ${accountCode} to ${newType}`);
    }
    
    skipAnomaly(accountCode) {
        this.resolutionDecisions.push({
            type: 'balance',
            account_code: accountCode,
            action: 'skip',
            timestamp: new Date().toISOString()
        });
        
        // Hide the anomaly
        const anomalyItem = document.querySelector(`[data-anomaly-id="${accountCode}"]`).closest('.issue-item');
        anomalyItem.style.opacity = '0.5';
        anomalyItem.style.pointerEvents = 'none';
    }
    
    acceptAllSuggestions() {
        const integrityIssues = document.querySelectorAll('#integrity-issues .issue-item');
        let accepted = 0;
        
        integrityIssues.forEach(issue => {
            const select = issue.querySelector('.suggestion-select');
            const accountCode = select.dataset.issueId;
            const selectedCode = select.value;
            
            if (selectedCode) {
                this.acceptSuggestion(accountCode);
                accepted++;
            }
        });
        
        this.showSuccess(`Accepted ${accepted} suggestions`);
    }
    
    bulkReclassify() {
        const anomalies = document.querySelectorAll('#balance-anomalies .issue-item');
        let reclassified = 0;
        
        anomalies.forEach(anomaly => {
            const select = anomaly.querySelector('.suggestion-select');
            const accountCode = select.dataset.anomalyId;
            const newType = select.value;
            
            if (newType) {
                this.reclassifyAccount(accountCode);
                reclassified++;
            }
        });
        
        this.showSuccess(`Reclassified ${reclassified} accounts`);
    }
    
    async exportDecisions() {
        if (this.resolutionDecisions.length === 0) {
            this.showWarning('No decisions to export.');
            return;
        }
        
        const data = {
            decisions: this.resolutionDecisions,
            metadata: {
                timestamp: new Date().toISOString(),
                chart_file: this.chartFile?.name,
                trial_file: this.trialFile?.name,
                template: document.getElementById('template-select').value,
                industry: document.getElementById('industry-input').value
            }
        };
        
        const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `resolution_decisions_${new Date().toISOString().split('T')[0]}.json`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        
        this.showSuccess('Decisions exported successfully');
    }
    
    async proceedWithMapping() {
        this.showProcessing('Running mapping process...');
        
        try {
            const formData = new FormData();
            formData.append('chart_file', this.chartFile);
            formData.append('trial_file', this.trialFile);
            formData.append('template', document.getElementById('template-select').value);
            formData.append('industry', document.getElementById('industry-input').value);
            
            if (this.resolutionDecisions.length > 0) {
                formData.append('decisions', JSON.stringify(this.resolutionDecisions));
            }
            
            const response = await fetch('/process', {
                method: 'POST',
                body: formData
            });
            
            if (!response.ok) {
                throw new Error(`Processing failed: ${response.statusText}`);
            }
            
            const results = await response.json();
            this.showResults(results);
            
        } catch (error) {
            this.showError(`Processing failed: ${error.message}`);
        } finally {
            this.hideProcessing();
        }
    }
    
    showResults(results) {
        const section = document.getElementById('results-section');
        const content = document.getElementById('results-content');
        
        content.innerHTML = `
            <div class="results-grid">
                <div class="result-card">
                    <h3>✅ Processing Complete</h3>
                    <p><strong>Output File:</strong> ${results.output_file}</p>
                    <p><strong>Accounts Processed:</strong> ${results.accounts_processed}</p>
                    <p><strong>Mappings Applied:</strong> ${results.mappings_applied}</p>
                </div>
                <div class="result-card">
                    <h3>📊 Summary</h3>
                    <p><strong>Integrity Issues Resolved:</strong> ${results.integrity_resolved || 0}</p>
                    <p><strong>Balance Anomalies Addressed:</strong> ${results.balance_addressed || 0}</p>
                    <p><strong>Manual Reviews Required:</strong> ${results.manual_reviews || 0}</p>
                </div>
            </div>
            <div class="mt-20">
                <button type="button" class="btn btn-primary" onclick="location.reload()">
                    Process Another File
                </button>
            </div>
        `;
        
        section.style.display = 'block';
    }
    
    showProcessing(message) {
        const section = document.getElementById('processing-section');
        const messageEl = document.getElementById('processing-message');
        
        messageEl.textContent = message;
        section.style.display = 'block';
    }
    
    hideProcessing() {
        document.getElementById('processing-section').style.display = 'none';
    }
    
    showError(message) {
        this.showMessage(message, 'error');
    }
    
    showSuccess(message) {
        this.showMessage(message, 'success');
    }
    
    showWarning(message) {
        this.showMessage(message, 'warning');
    }
    
    showMessage(message, type) {
        // Remove existing messages
        document.querySelectorAll('.success-message, .error-message, .warning-message').forEach(el => {
            el.remove();
        });
        
        const messageEl = document.createElement('div');
        messageEl.className = `${type}-message`;
        messageEl.textContent = message;
        
        // Insert after the header, before the main content
        const header = document.querySelector('header');
        header.insertAdjacentElement('afterend', messageEl);
        
        // Scroll to the message
        messageEl.scrollIntoView({ behavior: 'smooth', block: 'start' });
        
        // Auto-remove after 5 seconds
        setTimeout(() => {
            if (messageEl.parentNode) {
                messageEl.remove();
            }
        }, 5000);
    }
}

// Initialize the application
const mapper = new ReportCodeMapper();
