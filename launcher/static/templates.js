/**
 * Template Loading System for MCP Testing Suite
 * Phase 2 Refactoring: Clean template management for modals and teasers
 */

// Template cache to avoid repeated network requests
const templateCache = {};

/**
 * Load a template from the templates directory
 * @param {string} templateName - Name of the template file (without .html extension)
 * @returns {Promise<string>} - The template HTML content
 */
async function loadTemplate(templateName) {
    // Return cached version if available
    if (templateCache[templateName]) {
        return templateCache[templateName];
    }
    
    try {
        const response = await fetch(`/static/templates/${templateName}.html`);
        if (!response.ok) {
            throw new Error(`Failed to load template: ${templateName}`);
        }
        
        const templateContent = await response.text();
        
        // Cache the template
        templateCache[templateName] = templateContent;
        
        return templateContent;
    } catch (error) {
        console.error(`Error loading template ${templateName}:`, error);
        return `<div class="error">Failed to load template: ${templateName}</div>`;
    }
}

/**
 * Show a modal using a template
 * @param {string} templateName - Name of the template to load
 * @param {Object} options - Optional configuration
 */
async function showModalFromTemplate(templateName, options = {}) {
    try {
        const templateHTML = await loadTemplate(templateName);
        
        // Insert the template into the DOM
        document.body.insertAdjacentHTML('beforeend', templateHTML);
        
        // Optional: Apply any custom configurations
        if (options.onShow) {
            options.onShow();
        }
        
        console.log(`✅ Showed modal from template: ${templateName}`);
    } catch (error) {
        console.error(`Failed to show modal from template ${templateName}:`, error);
        alert(`Error loading modal: ${templateName}`);
    }
}

/**
 * Close a modal by removing it from DOM
 * @param {string} modalId - ID of the modal element to remove
 */
function closeModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.remove();
        console.log(`✅ Closed modal: ${modalId}`);
    }
}

/**
 * Preload commonly used templates for better performance
 */
async function preloadTemplates() {
    const commonTemplates = [
        'mcp-basics-teaser',
        'explore-examples-teaser', 
        'troubleshooting-teaser'
    ];
    
    const loadPromises = commonTemplates.map(template => 
        loadTemplate(template).catch(error => 
            console.warn(`Failed to preload template ${template}:`, error)
        )
    );
    
    await Promise.all(loadPromises);
    console.log('✅ Common templates preloaded');
}

// Preload templates when the script loads
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', preloadTemplates);
} else {
    preloadTemplates();
}