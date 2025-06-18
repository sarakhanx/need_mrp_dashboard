/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class DeliveryHierarchyWidget extends Component {
    static template = "need_mrp_dashboard.DeliveryHierarchyTemplate";
    
    setup() {
        // console.log("=== DeliveryHierarchyWidget Setup ===");
        // console.log("Props:", this.props);
        
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.state = useState({
            deliveries: [],
            moOverview: null,
            expandedDeliveries: new Set(),
            expandedComponents: new Set(),
            loading: true,
        });
        
        onWillStart(async () => {
            await Promise.all([
                this.loadDeliveries(),
                this.loadMOOverview()
            ]);
        });
    }
    
    async loadDeliveries() {
        // console.log("=== Loading Deliveries ===");
        try {
            // แก้ไขการเข้าถึง context
            const deliveryIds = this.props.action?.context?.delivery_ids || 
                               this.props.context?.delivery_ids || 
                               [];
            
            // console.log("Delivery IDs:", deliveryIds);
            
            if (deliveryIds.length === 0) {
                console.log("No delivery IDs found");
                this.state.deliveries = [];
                this.state.loading = false;
                return;
            }
            
            // console.log("Searching for deliveries with IDs:", deliveryIds);
            
            // โหลดข้อมูล deliveries พร้อม moves
            const deliveries = await this.orm.searchRead(
                "stock.picking",
                [["id", "in", deliveryIds]],
                [
                    "name", "origin", "partner_id", "state", 
                    "scheduled_date", "date_done", "move_ids"
                ]
            );
            
            // console.log("Found deliveries:", deliveries);
            
            // โหลดข้อมูล moves สำหรับแต่ละ delivery
            for (const delivery of deliveries) {
                if (delivery.move_ids && delivery.move_ids.length > 0) {
                    console.log(`Loading moves for delivery ${delivery.name}:`, delivery.move_ids);
                    delivery.moves = await this.orm.searchRead(
                        "stock.move",
                        [["id", "in", delivery.move_ids]],
                        [
                            "product_id", "description_picking", "product_uom_qty",
                            "quantity", "product_uom", "state", "location_id", "location_dest_id",
                            "price_unit"
                        ]
                    );
                    
                    // ถ้า move ไม่มี price_unit ให้ดึงจาก product พร้อม internal reference
                    for (const move of delivery.moves) {
                        if (move.product_id) {
                            try {
                                const product = await this.orm.searchRead(
                                    "product.product",
                                    [["id", "=", move.product_id[0]]],
                                    ["list_price", "standard_price", "default_code", "description", "description_sale"]
                                );
                                if (product.length > 0) {
                                    const productData = product[0];
                                    // แยก price และ cost
                                    move.price_unit = move.price_unit || productData.list_price || 0; // ราคาขาย
                                    move.cost_unit = productData.standard_price || 0; // ราคาต้นทุน
                                    move.product_internal_ref = productData.default_code || '';
                                    move.product_description = productData.description || productData.description_sale || '';
                                    // สร้าง display name
                                    move.product_display_name = this.formatProductName(move.product_id[1], productData.default_code);
                                } else {
                                    move.price_unit = move.price_unit || 0;
                                    move.cost_unit = 0;
                                    move.product_internal_ref = '';
                                    move.product_description = '';
                                    move.product_display_name = move.product_id[1];
                                }
                            } catch (error) {
                                console.error(`Error loading product data for ${move.product_id[1]}:`, error);
                                move.price_unit = move.price_unit || 0;
                                move.cost_unit = 0;
                                move.product_internal_ref = '';
                                move.product_description = '';
                                move.product_display_name = move.product_id[1];
                            }
                        }
                    }
                    
                    // console.log(`Moves for ${delivery.name}:`, delivery.moves);
                } else {
                    delivery.moves = [];
                }
            }
            
            this.state.deliveries = deliveries;
            this.state.loading = false;
            
            // console.log("Final state:", this.state);
            
        } catch (error) {
            console.error("Error loading deliveries:", error);
            this.state.deliveries = [];
            this.state.loading = false;
        }
    }
    
    async loadMOOverview() {
        console.log("=== Loading MO Overview ===");
        try {
            const moId = this.props.action?.context?.default_mo_id || 
                        this.props.context?.default_mo_id;
            
            if (!moId) {
                console.log("No MO ID found for overview");
                return;
            }
            
            // console.log("Loading MO Overview for ID:", moId);
            
            // เรียก method ที่ return MO overview data (similar to Odoo's overview)
            const overviewData = await this.orm.call(
                "mrp.production",
                "get_mo_overview_data",
                [moId],
                {}
            );
            
            // console.log("MO Overview data:", overviewData);
            this.state.moOverview = overviewData;
            
        } catch (error) {
            console.error("Error loading MO overview:", error);
            // ถ้า method ยังไม่มี ให้สร้าง mock data
            this.state.moOverview = await this.createMockOverviewData();
        }
        
        // Ensure safe structure
        if (this.state.moOverview) {
            this.state.moOverview.components = this.state.moOverview.components || [];
            this.state.moOverview.operations = this.state.moOverview.operations || { summary: {}, details: [] };
            
            // Ensure each component has sub_mos array
            this.state.moOverview.components.forEach(component => {
                component.sub_mos = component.sub_mos || [];
            });
        }
    }
    
    async createMockOverviewData() {
        try {
            const moId = this.props.action?.context?.default_mo_id || 
                        this.props.context?.default_mo_id;
            
            // ดึงข้อมูล MO พื้นฐาน
            const mo = await this.orm.searchRead(
                "mrp.production",
                [["id", "=", moId]],
                ["name", "product_id", "product_qty", "product_uom_id", "state", "move_raw_ids"]
            );
            
            if (mo.length === 0) return null;
            
            const moData = mo[0];
            
            // ดึงข้อมูล components พร้อม product details
            let components = [];
            if (moData.move_raw_ids && moData.move_raw_ids.length > 0) {
                const rawMoves = await this.orm.searchRead(
                    "stock.move",
                    [["id", "in", moData.move_raw_ids]],
                    ["product_id", "product_uom_qty", "quantity", "state", "reserved_availability"]
                );
                
                // ดึงข้อมูล product details สำหรับแต่ละ component
                for (const move of rawMoves) {
                    let productDisplayName = move.product_id[1];
                    let productDescription = '';
                    
                    if (move.product_id) {
                        try {
                            const product = await this.orm.searchRead(
                                "product.product",
                                [["id", "=", move.product_id[0]]],
                                ["default_code", "description", "description_sale", "standard_price"]
                            );
                            if (product.length > 0) {
                                const productData = product[0];
                                productDisplayName = this.formatProductName(move.product_id[1], productData.default_code);
                                productDescription = productData.description || productData.description_sale || '';
                            }
                        } catch (error) {
                            console.error(`Error loading product details for ${move.product_id[1]}:`, error);
                        }
                    }
                    
                    components.push({
                        summary: {
                            id: move.id,
                            name: productDisplayName,
                            product_id: move.product_id[0],
                            quantity: move.product_uom_qty,
                            uom_name: "Units",
                            quantity_on_hand: 0,
                            quantity_reserved: move.reserved_availability || 0,
                            state: move.state,
                            formatted_state: this.formatState(move.state),
                            mo_cost: 0,
                            description: productDescription
                        },
                        sub_mos: []
                    });
                }
            }
            
            return {
                summary: {
                    name: moData.product_id[1],
                    quantity: moData.product_qty,
                    uom_name: moData.product_uom_id[1],
                    state: moData.state,
                    formatted_state: this.formatState(moData.state),
                    mo_cost: 0
                },
                components: components
            };
            
        } catch (error) {
            console.error("Error creating mock overview data:", error);
            return null;
        }
    }
    
    formatProductName(productName, internalRef) {
        /**
         * Format product name with internal reference like [AA-065] ทินเนอร์ 3 A
         */
        if (internalRef && internalRef.trim()) {
            return `[${internalRef}] ${productName}`;
        }
        return productName;
    }
    
    formatState(state) {
        const stateMap = {
            'draft': 'Draft',
            'confirmed': 'Confirmed',
            'progress': 'In Progress',
            'to_close': 'To Close',
            'done': 'Done',
            'cancel': 'Cancelled'
        };
        return stateMap[state] || state;
    }
    
    getStatusColor(state) {
        const colorMap = {
            'draft': 'info',
            'confirmed': 'warning',
            'progress': 'primary',
            'to_close': 'success',
            'done': 'success',
            'cancel': 'danger',
            'to_order': 'warning',
            'unavailable': 'danger'
        };
        return colorMap[state] || 'secondary';
    }
    
    toggleDelivery(deliveryId) {
        console.log("Toggle delivery:", deliveryId);
        if (this.state.expandedDeliveries.has(deliveryId)) {
            this.state.expandedDeliveries.delete(deliveryId);
        } else {
            this.state.expandedDeliveries.add(deliveryId);
        }
    }
    
    isExpanded(deliveryId) {
        return this.state.expandedDeliveries.has(deliveryId);
    }
    
    toggleComponent(componentId) {
        console.log("Toggle component:", componentId);
        if (this.state.expandedComponents.has(componentId)) {
            this.state.expandedComponents.delete(componentId);
        } else {
            this.state.expandedComponents.add(componentId);
        }
    }
    
    isComponentExpanded(componentId) {
        return this.state.expandedComponents.has(componentId);
    }
    
    getStatusBadgeClass(state) {
        const statusClasses = {
            'done': 'badge-success',
            'draft': 'badge-info',
            'waiting': 'badge-warning',
            'confirmed': 'badge-warning',
            'assigned': 'badge-primary',
            'cancel': 'badge-danger',
        };
        return `badge badge-pill ${statusClasses[state] || 'badge-secondary'}`;
    }
    
    formatDate(dateString) {
        if (!dateString) return '-';
        return new Date(dateString).toLocaleString('th-TH', {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit'
        });
    }
    
    formatCurrency(amount) {
        return new Intl.NumberFormat('th-TH', {
            style: 'currency',
            currency: 'THB',
            minimumFractionDigits: 2
        }).format(amount);
    }

    openDeliveryDocument(ev) {
        const deliveryId = ev.currentTarget.dataset.deliveryId;
        if (deliveryId) {
            this.actionService.doAction({
                type: 'ir.actions.act_window',
                res_model: 'stock.picking',
                res_id: parseInt(deliveryId),
                views: [[false, 'form']],
                target: 'current',
            });
        }
    }

    openMODocument(ev) {
        ev.preventDefault();
        ev.stopPropagation();
        const moId = ev.currentTarget.dataset.moId;
        console.log("Opening MO document for ID:", moId);
        
        if (moId && moId !== '9999') { // Skip mock data
            this.actionService.doAction({
                type: 'ir.actions.act_window',
                res_model: 'mrp.production',
                res_id: parseInt(moId),
                views: [[false, 'form']],
                target: 'current',
            });
        } else if (moId === '9999') {
            // Handle mock data - show notification
            this.actionService.doAction({
                type: 'ir.actions.client',
                tag: 'display_notification',
                params: {
                    title: 'Mock Data',
                    message: 'นี่คือข้อมูลจำลอง ไม่สามารถเปิดได้',
                    type: 'info',
                }
            });
        }
    }

    // Cost calculation methods
    calculateMOTotalCost() {
        if (!this.state.moOverview) return 0;
        
        let totalCost = 0;
        
        // ไม่นับ Main MO cost เพราะจะซ้ำกับ Components
        // totalCost += this.state.moOverview.summary?.mo_cost || 0;
        
        // Components cost (นี่คือต้นทุนหลักของ MO)
        if (this.state.moOverview.components) {
            for (const component of this.state.moOverview.components) {
                totalCost += component.summary?.mo_cost || 0;
                
                // Sub MOs cost (เฉพาะ Sub MOs ไม่นับ components ของ Sub MO เพราะจะซ้ำ)
                if (component.sub_mos) {
                    for (const subMo of component.sub_mos) {
                        totalCost += subMo.total_cost || 0;
                    }
                }
            }
        }
        
        // Operations cost (เพิ่มต้นทุนการดำเนินการ)
        totalCost += this.state.moOverview.operations?.summary?.mo_cost || 0;
        
        return totalCost;
    }

    calculateDeliveriesTotalCost() {
        if (!this.state.deliveries || this.state.deliveries.length === 0) return 0;
        
        let totalCost = 0;
        
        for (const delivery of this.state.deliveries) {
            if (delivery.moves) {
                for (const move of delivery.moves) {
                    const quantity = move.product_uom_qty || 0;
                    const costUnit = move.cost_unit || 0;
                    totalCost += quantity * costUnit;
                }
            }
        }
        
        return totalCost;
    }

    calculateGrandTotalCost() {
        const moCost = this.calculateMOTotalCost();
        const deliveriesCost = this.calculateDeliveriesTotalCost();
        return moCost + deliveriesCost;
    }

    getCostSummary() {
        const moCost = this.calculateMOTotalCost();
        const deliveriesCost = this.calculateDeliveriesTotalCost();
        const grandTotal = moCost + deliveriesCost;
        
        return {
            moCost: moCost,
            deliveriesCost: deliveriesCost,
            grandTotal: grandTotal,
            moPercentage: grandTotal > 0 ? (moCost / grandTotal * 100) : 0,
            deliveriesPercentage: grandTotal > 0 ? (deliveriesCost / grandTotal * 100) : 0
        };
    }

    getCostBreakdown() {
        if (!this.state.moOverview) return null;
        
        let componentsCost = 0;
        let subMosCost = 0;
        let operationsCost = 0;
        let deliveriesCost = this.calculateDeliveriesTotalCost();
        
        // คำนวณต้นทุน Components
        if (this.state.moOverview.components) {
            for (const component of this.state.moOverview.components) {
                componentsCost += component.summary?.mo_cost || 0;
                
                // คำนวณต้นทุน Sub MOs แยกต่างหาก
                if (component.sub_mos) {
                    for (const subMo of component.sub_mos) {
                        subMosCost += subMo.total_cost || 0;
                    }
                }
            }
        }
        
        // คำนวณต้นทุน Operations
        operationsCost = this.state.moOverview.operations?.summary?.mo_cost || 0;
        
        const totalMoCost = componentsCost + subMosCost + operationsCost;
        const grandTotal = totalMoCost + deliveriesCost;
        
        return {
            componentsCost: componentsCost,
            subMosCost: subMosCost,
            operationsCost: operationsCost,
            totalMoCost: totalMoCost,
            deliveriesCost: deliveriesCost,
            grandTotal: grandTotal
        };
    }

    async exportToExcel() {
        console.log("Exporting to Excel...");
        
        try {
            const moId = this.props.action?.context?.default_mo_id || 
                        this.props.context?.default_mo_id;
            
            if (!moId) {
                this.actionService.doAction({
                    type: 'ir.actions.client',
                    tag: 'display_notification',
                    params: {
                        title: 'Export Error',
                        message: 'ไม่พบ MO ID สำหรับ export',
                        type: 'warning',
                    }
                });
                return;
            }
            
            // แสดง loading notification
            this.actionService.doAction({
                type: 'ir.actions.client',
                tag: 'display_notification',
                params: {
                    title: 'Exporting...',
                    message: 'กำลังสร้างไฟล์ Excel กรุณารอสักครู่',
                    type: 'info',
                }
            });
            
            // เรียก Python method
            const result = await this.orm.call(
                "mrp.production",
                "action_export_mo_overview_excel",
                [moId],
                {}
            );
            
            if (result.type === 'ir.actions.act_url') {
                // เปิดลิงก์ download
                window.open(result.url, '_blank');
                
                this.actionService.doAction({
                    type: 'ir.actions.client',
                    tag: 'display_notification',
                    params: {
                        title: 'Export Success',
                        message: 'ไฟล์ Excel ถูกสร้างเรียบร้อยแล้ว',
                        type: 'success',
                    }
                });
            } else {
                // แสดง error หรือ warning จาก Python
                this.actionService.doAction(result);
            }
            
        } catch (error) {
            console.error("Export error:", error);
            this.actionService.doAction({
                type: 'ir.actions.client',
                tag: 'display_notification',
                params: {
                    title: 'Export Error',
                    message: `เกิดข้อผิดพลาดในการ export: ${error.message}`,
                    type: 'error',
                }
            });
        }
    }
}

registry.category("actions").add("delivery_hierarchy", DeliveryHierarchyWidget); 