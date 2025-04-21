/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { loadJS } from "@web/core/assets";
const { Component, onWillStart, useRef, onMounted, useState } = owl;

export class ChartsDashboard extends Component {
    static template = "need_mrp_dashboard.ChartsDashboard";

    setup() {
        this.chartRef = useRef("chart");
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.dialog = useService("dialog");
        this.action = useService("action");

        // Initialize with today's date
        const today = new Date();
        const firstDayOfMonth = new Date(today.getFullYear(), today.getMonth(), 1);

        this.state = useState({
            startDate: this.formatDateForAPI(firstDayOfMonth),
            endDate: this.formatDateForAPI(today),
            recentMOs: [],
            operationTypes: [],
            selectedOperationType: '',
            operationDocs: [],
            chartData: {
                labels: [],
                datasets: [
                    {
                        label: "ร่าง (Draft)",
                        data: [],
                        borderColor: "rgb(128, 128, 128)",
                        backgroundColor: "rgba(128, 128, 128, 0.1)",
                        borderWidth: 2,
                        tension: 0.4
                    },
                    {
                        label: "ยืนยันแล้ว (Confirmed)",
                        data: [],
                        borderColor: "rgb(54, 162, 235)",
                        backgroundColor: "rgba(54, 162, 235, 0.1)",
                        borderWidth: 2,
                        tension: 0.4
                    },
                    {
                        label: "กำลังดำเนินการ (In Progress)",
                        data: [],
                        borderColor: "rgb(255, 206, 86)",
                        backgroundColor: "rgba(255, 206, 86, 0.1)",
                        borderWidth: 2,
                        tension: 0.4
                    },
                    {
                        label: "เสร็จสิ้น (Done)",
                        data: [],
                        borderColor: "rgb(75, 192, 192)",
                        backgroundColor: "rgba(75, 192, 192, 0.1)",
                        borderWidth: 2,
                        tension: 0.4
                    },
                    {
                        label: "ยกเลิก (Cancelled)",
                        data: [],
                        borderColor: "rgb(255, 99, 132)",
                        backgroundColor: "rgba(255, 99, 132, 0.1)",
                        borderWidth: 2,
                        tension: 0.4
                    }
                ]
            }
        });

        onWillStart(async () => {
            console.log('Starting to load Chart.js from CDN...');
            await loadJS("https://cdn.jsdelivr.net/npm/chart.js");
            await this.loadOperationTypes();
            console.log('Chart.js loaded successfully');
        });

        onMounted(() => {
            console.log('Component mounted, starting to load data...');
            setTimeout(() => {
                this.loadAndRenderChart();
                this.loadRecentMOs();
            }, 100);
        });
    }

    // Format date for display in table
    formatDate(dateStr) {
        if (!dateStr) return '';
        const date = new Date(dateStr);
        return date.toLocaleDateString('th-TH', {
            year: 'numeric',
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
    }

    // Get status class for badge
    getStatusClass(state) {
        const classes = {
            'draft': 'bg-secondary',
            'confirmed': 'bg-primary',
            'progress': 'bg-warning',
            'done': 'bg-success',
            'cancel': 'bg-danger'
        };
        return classes[state] || 'bg-secondary';
    }

    // Get status text in Thai and English
    getStatusText(state) {
        const texts = {
            'draft': 'ร่าง / Draft',
            'confirmed': 'ยืนยันแล้ว / Confirmed',
            'progress': 'กำลังดำเนินการ / In Progress',
            'done': 'เสร็จสิ้น / Done',
            'cancel': 'ยกเลิก / Cancelled'
        };
        return texts[state] || state;
    }

    // Load recent MOs
    async loadRecentMOs() {
        try {
            const recentMOs = await this.orm.searchRead(
                "mrp.production",
                [['date_finished', '!=', false]],
                [
                    'name', 'product_id', 'product_qty', 'product_uom_id',
                    'date_start', 'date_finished', 'state'
                ],
                {
                    order: 'date_finished desc',
                    limit: 15
                }
            );
            this.state.recentMOs = recentMOs;
        } catch (error) {
            console.error('Error loading recent MOs:', error);
            this.notification.add(
                `Error loading recent MOs: ${error.message || error}`,
                { type: "danger" }
            );
        }
    }

    // Load operation types
    async loadOperationTypes() {
        try {
            const types = await this.orm.searchRead(
                "stock.picking.type",
                [['code', 'in', ['mrp_operation', 'incoming', 'outgoing']]],
                ['name', 'code', 'warehouse_id']
            );
            this.state.operationTypes = types;
        } catch (error) {
            console.error('Error loading operation types:', error);
            this.notification.add(
                `Error loading operation types: ${error.message || error}`,
                { type: "danger" }
            );
        }
    }

    formatDateForAPI(date) {
        if (!date) return null;
        
        // Ensure we have a valid date object
        const dateObj = date instanceof Date ? date : new Date(date);
        
        // Check if date is valid
        if (isNaN(dateObj.getTime())) {
            console.error("Invalid date:", date);
            return null;
        }
        
        // Format as YYYY-MM-DD
        const year = dateObj.getFullYear();
        const month = String(dateObj.getMonth() + 1).padStart(2, '0');
        const day = String(dateObj.getDate()).padStart(2, '0');
        
        return `${year}-${month}-${day}`;
    }

    async onDateChange() {
        await this.loadAndRenderChart();
        await this.loadRecentMOs();
    }

    async loadAndRenderChart() {
        try {
            console.log('Loading dashboard data...');
            // Generate data first
            await this.orm.call(
                "custom.mo.dashboard",
                "generate_data",
                [this.state.startDate, this.state.endDate]
            );
            
            // Then fetch all records
            const records = await this.orm.searchRead(
                "custom.mo.dashboard",
                [
                    ['date', '>=', this.state.startDate],
                    ['date', '<=', this.state.endDate]
                ],
                ["date", "draft", "confirmed", "progress", "done", "cancel"],
                { order: "date asc" }
            );
            
            // Process data for chart
            this.state.chartData.labels = records.map(r => r.date);
            this.state.chartData.datasets[0].data = records.map(r => r.draft);
            this.state.chartData.datasets[1].data = records.map(r => r.confirmed);
            this.state.chartData.datasets[2].data = records.map(r => r.progress);
            this.state.chartData.datasets[3].data = records.map(r => r.done);
            this.state.chartData.datasets[4].data = records.map(r => r.cancel);
            
            console.log('Data received:', this.state.chartData);
            this.renderChart();
        } catch (error) {
            console.error('Error loading data:', error);
            this.notification.add(
                `Error loading dashboard data: ${error.message || error}`,
                { type: "danger", sticky: true }
            );
        }
    }

    renderChart() {
        if (!this.chartRef.el) {
            console.error('Canvas element not found');
            return;
        }

        try {
            console.log('Starting to render chart...');
            if (this.chart) {
                this.chart.destroy();
            }

            // Set canvas dimensions explicitly
            const container = this.chartRef.el.parentElement;
            this.chartRef.el.style.height = '400px';
            this.chartRef.el.style.width = '100%';

            this.chart = new Chart(this.chartRef.el, {
                type: 'line',
                data: this.state.chartData,
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    interaction: {
                        mode: 'index',
                        intersect: false
                    },
                    elements: {
                        point: {
                            radius: 5,
                            hoverRadius: 8,
                            borderWidth: 2,
                            backgroundColor: 'white'
                        },
                        line: {
                            tension: 0.3
                        }
                    },
                    plugins: {
                        legend: {
                            position: 'bottom',
                            labels: {
                                padding: 20,
                                usePointStyle: true,
                                pointStyle: 'circle'
                            },
                            onClick: (evt, legendItem, legend) => {
                                const index = legendItem.datasetIndex;
                                const ci = legend.chart;
                                const meta = ci.getDatasetMeta(index);
                                
                                meta.hidden = meta.hidden === null ? !ci.data.datasets[index].hidden : null;
                                
                                // Apply animation when toggling visibility
                                ci.update('active');
                            }
                        },
                        title: {
                            display: true,
                            text: 'สถานะใบสั่งผลิต (Manufacturing Orders Status)',
                            position: 'top',
                            font: {
                                size: 16,
                                weight: 'bold'
                            },
                            padding: {
                                top: 10,
                                bottom: 30
                            }
                        },
                        tooltip: {
                            mode: 'index',
                            intersect: false
                        }
                    },
                    scales: {
                        y: {
                            beginAtZero: true,
                            grid: {
                                drawBorder: false,
                                color: 'rgba(0, 0, 0, 0.1)'
                            },
                            ticks: {
                                stepSize: 1
                            },
                            title: {
                                display: true,
                                text: 'จำนวนใบสั่งผลิต',
                                font: {
                                    weight: 'bold'
                                }
                            }
                        },
                        x: {
                            grid: {
                                drawBorder: false,
                                color: 'rgba(0, 0, 0, 0.1)'
                            },
                            title: {
                                display: true,
                                text: 'วันที่',
                                font: {
                                    weight: 'bold'
                                }
                            }
                        }
                    },
                    layout: {
                        padding: {
                            left: 10,
                            right: 10,
                            top: 0,
                            bottom: 0
                        }
                    }
                }
            });

            console.log('Chart rendered successfully');
        } catch (error) {
            console.error('Error rendering chart:', error);
            this.notification.add(
                `Error rendering chart: ${error.message || error}`,
                { type: "danger", sticky: true }
            );
        }
    }

    willDestroy() {
        if (this.chart) {
            this.chart.destroy();
        }
    }

    // Handle operation type change
    async onOperationTypeChange() {
        if (!this.state.selectedOperationType) {
            this.state.operationDocs = [];
            return;
        }
        await this.loadOperationDocuments();
    }

    // Load operation documents
    async loadOperationDocuments() {
        try {
            const selectedType = this.state.operationTypes.find(
                t => t.id === parseInt(this.state.selectedOperationType)
            );
            
            if (!selectedType) return;

            let docs = [];
            if (selectedType.code === 'mrp_operation') {
                docs = await this.orm.searchRead(
                    "mrp.production",
                    [['picking_type_id', '=', selectedType.id]],
                    [
                        'name', 'date_start', 'product_id', 
                        'product_qty', 'product_uom_id', 'warehouse_id', 
                        'state'
                    ],
                    { order: 'name desc' }
                );
            } else {
                docs = await this.orm.searchRead(
                    "stock.picking",
                    [['picking_type_id', '=', selectedType.id]],
                    [
                        'name', 'scheduled_date', 'product_id', 
                        'product_uom_qty', 'product_uom_id', 
                        'warehouse_id', 'state'
                    ],
                    { order: 'name desc' }
                );
            }
            this.state.operationDocs = docs;
        } catch (error) {
            console.error('Error loading operation documents:', error);
            this.notification.add(
                `Error loading documents: ${error.message || error}`,
                { type: "danger" }
            );
        }
    }

    // Refresh operations
    async onRefreshOperations() {
        await this.loadOperationDocuments();
    }

    // Navigate to document
    async navigateToDocument(docType, docId) {
        try {
            const action = {
                type: 'ir.actions.act_window',
                res_model: docType,
                res_id: docId,
                views: [[false, 'form']],
                target: 'current',
            };
            await this.action.doAction(action);
        } catch (error) {
            console.error('Error navigating to document:', error);
            this.notification.add(
                `Error opening document: ${error.message || error}`,
                { type: "danger" }
            );
        }
    }

    // Handle row click for MO
    async onMORowClick(moId) {
        await this.navigateToDocument('mrp.production', moId);
    }

    // Handle row click for operation document
    async onOperationDocRowClick(doc) {
        const selectedType = this.state.operationTypes.find(
            t => t.id === parseInt(this.state.selectedOperationType)
        );
        
        if (!selectedType) return;

        const docType = selectedType.code === 'mrp_operation' ? 'mrp.production' : 'stock.picking';
        await this.navigateToDocument(docType, doc.id);
    }
}

// Register the client action directly
registry.category("actions").add("need_mrp_dashboard.ChartsDashboard", ChartsDashboard);

// Also register as a client action with a specific ID
registry.category("client_actions").add("need_mrp_dashboard.ChartsDashboard", {
    id: "need_mrp_dashboard.ChartsDashboard",
    component: ChartsDashboard,
});