<template>
  <div class="nb-page hazard-page">
    <!-- 页头：标题 + AI 识别 / 上报记录 模式切换 -->
    <div class="nb-page-head">
      <div class="head-left">
        <div class="head-icon">
          <el-icon :size="22"><Aim /></el-icon>
        </div>
        <div class="head-text">
          <div class="head-title-row">
            <h1 class="nb-title">隐患管理中心</h1>
            <span class="nb-chip nb-chip--danger">AI 视觉巡检</span>
          </div>
          <p class="head-sub">工程建设项目实时视觉安全诊断、结构缺陷探伤与合规派工闭环系统</p>
        </div>
      </div>
      <div class="mode-switch">
        <button
          type="button"
          class="mode-btn"
          :class="{ active: activeTab === 'detect' }"
          @click="activeTab = 'detect'"
        >
          <el-icon><Camera /></el-icon>
          <span>AI 识别上报</span>
        </button>
        <button
          type="button"
          class="mode-btn"
          :class="{ active: activeTab === 'records' }"
          @click="activeTab = 'records'; onTabChange('records')"
        >
          <el-icon><Tickets /></el-icon>
          <span>隐患上报记录</span>
          <span class="mode-count nb-mono">{{ total }}</span>
        </button>
      </div>
    </div>

    <!-- ===== AI 识别上报：三栏工作台 ===== -->
    <div v-if="activeTab === 'detect'" class="workspace-grid">
      <!-- 左栏：巡检记录 -->
      <section class="nb-panel rail">
        <div class="nb-panel-head">
          <div class="nb-panel-title">
            巡检记录
            <span class="count-chip nb-mono">{{ historyList.length }}</span>
          </div>
          <button
            v-if="historySelectedIds.length"
            type="button"
            class="mini-danger"
            @click="onBatchDeleteHistory"
          >
            <el-icon><Delete /></el-icon>删除({{ historySelectedIds.length }})
          </button>
        </div>
        <div class="rail-search">
          <el-input v-model="historyKeyword" size="small" placeholder="检索隐患标题…" clearable>
            <template #prefix>
              <el-icon><Search /></el-icon>
            </template>
          </el-input>
        </div>
        <div class="rail-list">
          <div v-if="!filteredHistoryList.length" class="nb-empty">暂无隐患记录</div>
          <div
            v-for="item in filteredHistoryList"
            :key="item.id"
            class="rail-card"
            :class="{ active: item.id === activeHistoryId }"
          >
            <el-checkbox
              class="rail-check"
              :model-value="historySelectedIds.includes(item.id)"
              size="small"
              @click.stop
              @change="(val: boolean) => onToggleHistoryItem(item.id, val)"
            />
            <div class="rail-body" @click="onSelectHistory(item)">
              <div class="rail-meta">
                <span class="nb-chip" :class="levelChipMap[item.raw?.level] || 'nb-chip--neutral'">
                  <span class="chip-dot"></span>{{ item.raw?.level ? levelText(item.raw.level) : '未分级' }}
                </span>
                <span class="rail-time nb-mono">{{ formatTime(item.raw?.created_at).slice(5, 16) }}</span>
              </div>
              <div class="rail-title">{{ item.title }}</div>
              <div class="rail-sub">
                {{ statusText(item.raw?.status) }} · {{ item.raw?.category || '未分类' }}
              </div>
            </div>
            <button type="button" class="rail-del" title="删除" @click.stop="onDeleteHistoryItem(item.id)">
              <el-icon><Delete /></el-icon>
            </button>
          </div>
        </div>
        <div class="rail-foot nb-mono">
          <span>已选 {{ historySelectedIds.length }} 条</span>
          <span>共 {{ historyList.length }} 条</span>
        </div>
      </section>

      <!-- 中栏：图片识别工作区 -->
      <section class="nb-panel center">
        <div class="nb-panel-head center-head">
          <div class="nb-panel-title">
            隐患图片识别
            <span class="engine-chip nb-mono">AI 视觉引擎</span>
          </div>
          <el-upload
            v-if="uploaded"
            :auto-upload="false"
            :limit="9"
            accept="image/*"
            :show-file-list="false"
            :on-change="onUpload"
            :disabled="detecting"
          >
            <el-button size="small" :loading="detecting">
              <el-icon v-if="!detecting"><Upload /></el-icon>
              {{ detecting ? '识别中…' : '重新上传' }}
            </el-button>
          </el-upload>
        </div>

        <div class="stage">
          <div v-if="!uploaded" class="stage-empty">
            <el-icon :size="44"><Picture /></el-icon>
            <div class="stage-empty-main">请上传图片（最多 9 张）</div>
            <div class="stage-empty-sub">上传后系统将自动识别隐患并标注</div>
            <el-upload
              :auto-upload="false"
              :limit="9"
              accept="image/*"
              :show-file-list="false"
              :on-change="onUpload"
              :disabled="detecting"
            >
              <el-button type="primary" :loading="detecting">
                <el-icon v-if="!detecting"><Upload /></el-icon>
                {{ detecting ? '识别中…' : '上传图片' }}
              </el-button>
            </el-upload>
          </div>

          <div v-else class="image-frame">
            <img v-if="annotatedUrl" :src="annotatedUrl" class="site-image" alt="隐患标注图" />
            <div v-else class="loading-state">
              <div class="loading-spinner"></div>
              <div class="loading-text">图片加载中…</div>
            </div>
            <div v-if="annotatedUrl && detections.length" class="hud nb-mono">
              <span class="hud-dot"></span>已锁定 {{ detections.length }} 处异常
            </div>
          </div>
        </div>

        <div class="meta-strip">
          <div class="meta-cell">
            <span class="meta-label">记录编号</span>
            <span class="meta-value nb-mono" :title="activeHistoryId">{{ activeHistoryId || '未保存' }}</span>
          </div>
          <div class="meta-cell">
            <span class="meta-label">识别隐患</span>
            <span class="meta-value">{{ detections.length }} 项</span>
          </div>
          <div class="meta-cell">
            <span class="meta-label">置信均值</span>
            <span class="meta-value nb-mono">{{ avgConfText }}</span>
          </div>
          <div class="meta-cell">
            <span class="meta-label">最高风险</span>
            <span class="meta-value">{{ topRiskText }}</span>
          </div>
        </div>
      </section>

      <!-- 右栏：AI 智能分析报告 -->
      <aside class="nb-panel report">
        <div class="nb-panel-head">
          <div class="nb-panel-title">AI 智能分析报告</div>
          <span
            v-if="detections.length"
            class="nb-chip"
            :class="riskChipMap[topRisk] || 'nb-chip--neutral'"
          >风险等级: {{ riskText(topRisk) }}</span>
        </div>
        <div class="report-body">
          <div v-if="!uploaded && !detections.length" class="nb-empty">
            <span>暂无分析结果</span>
            <span class="empty-sub">上传图片后自动生成</span>
          </div>
          <template v-else>
            <div class="overview">
              <div class="overview-head">
                <span>检测诊断综述</span>
                <span class="nb-mono">置信均值 {{ avgConfText }}</span>
              </div>
              <div class="overview-grid">
                <div class="stat">
                  <span class="stat-label">发现隐患</span>
                  <span class="stat-value" :class="{ 'is-danger': detections.length > 0 }">{{ detections.length }} 项</span>
                </div>
                <div class="stat">
                  <span class="stat-label">最高等级</span>
                  <span class="stat-value">{{ topRiskText }}</span>
                </div>
                <div class="stat">
                  <span class="stat-label">平均置信</span>
                  <span class="stat-value nb-mono">{{ avgConfText }}</span>
                </div>
              </div>
            </div>

            <div v-if="detecting" class="nb-empty">
              <span>AI 正在识别，请稍候…</span>
            </div>
            <div v-else-if="!detections.length" class="nb-empty">
              <span>未识别到明显隐患</span>
              <span class="empty-sub">可重新上传更清晰的现场照片</span>
            </div>

            <div v-for="(d, i) in detections" :key="i" class="det-card">
              <div class="det-head">
                <span class="nb-chip" :class="riskChipMap[d.risk] || 'nb-chip--neutral'">
                  {{ riskText(d.risk) }} · 隐患 {{ i + 1 }}
                </span>
                <span class="conf nb-mono">置信度 {{ Math.round((d.conf || 0) * 100) }}%</span>
              </div>
              <div class="det-name">{{ d.label }}</div>
              <div v-if="d.note" class="det-row">
                <span class="det-key">物理位置</span>
                <span>{{ d.note }}</span>
              </div>
              <div v-if="d.fix" class="det-fix" :class="'fix-' + (d.risk || 'low')">
                <span class="det-key">规范整改建议</span>
                <span>{{ d.fix }}</span>
              </div>
            </div>

            <button v-if="detections.length" type="button" class="btn-dispatch" @click="openReportDialog">
              <el-icon><Promotion /></el-icon>
              补全信息并上报
            </button>
          </template>
        </div>
      </aside>
    </div>

    <!-- ===== 隐患上报记录：三栏工作台 ===== -->
    <div v-else class="workspace-grid">
      <!-- 左栏：隐患列表 -->
      <section class="nb-panel rail">
        <div class="nb-panel-head">
          <div class="nb-panel-title">
            隐患列表
            <span class="count-chip nb-mono">{{ recordsList.length }}</span>
          </div>
          <button
            v-if="recordsSelectedIds.length"
            type="button"
            class="mini-danger"
            @click="onBatchDeleteRecords"
          >
            <el-icon><Delete /></el-icon>删除({{ recordsSelectedIds.length }})
          </button>
        </div>
        <div class="rail-list">
          <div v-if="!recordsList.length" class="nb-empty">暂无隐患记录</div>
          <div
            v-for="item in recordsList"
            :key="item.id"
            class="rail-card"
            :class="{ active: item.id === activeRecordId }"
          >
            <el-checkbox
              class="rail-check"
              :model-value="recordsSelectedIds.includes(item.id)"
              size="small"
              @click.stop
              @change="(val: boolean) => onToggleRecordsItem(item.id, val)"
            />
            <div class="rail-body" @click="onSelectRecord(item)">
              <div class="rail-meta">
                <span class="nb-chip" :class="levelChipMap[item.level] || 'nb-chip--neutral'">
                  <span class="chip-dot"></span>{{ levelText(item.level) }}
                </span>
                <span class="rail-time nb-mono">{{ formatTime(item.created_at).slice(5, 16) }}</span>
              </div>
              <div class="rail-title">{{ item.title }}</div>
              <div class="rail-sub">{{ statusText(item.status) }} · {{ item.reporter_name || '未上报' }}</div>
            </div>
            <button type="button" class="rail-del" title="删除" @click.stop="onDeleteRecordsItem(item.id)">
              <el-icon><Delete /></el-icon>
            </button>
          </div>
        </div>
        <div class="rail-foot nb-mono">
          <span>已选 {{ recordsSelectedIds.length }} 条</span>
          <span>共 {{ total }} 条</span>
        </div>
      </section>

      <!-- 中栏：记录表格 -->
      <section class="nb-panel center">
        <div class="nb-panel-head">
          <div class="nb-panel-title">
            隐患上报记录
            <span class="count-chip nb-mono">{{ total }}</span>
          </div>
          <el-button type="primary" size="small" @click="openManualReportDialog">手动上报</el-button>
        </div>

        <div class="records-toolbar">
          <el-select v-model="filterStatus" placeholder="状态筛选" clearable size="small" style="width: 120px" @change="loadRecords">
            <el-option label="待处理" value="pending" />
            <el-option label="处理中" value="processing" />
            <el-option label="待验收" value="pending_review" />
            <el-option label="已闭环" value="closed" />
            <el-option label="已驳回" value="rejected" />
          </el-select>
          <el-select v-model="filterLevel" placeholder="等级筛选" clearable size="small" style="width: 120px" @change="loadRecords">
            <el-option label="重大" value="critical" />
            <el-option label="较大" value="major" />
            <el-option label="一般" value="general" />
            <el-option label="轻微" value="minor" />
          </el-select>
        </div>

        <div class="records-table-wrap">
          <el-table
            :data="recordsList"
            stripe
            height="100%"
            highlight-current-row
            @row-click="onSelectRecord"
            style="width: 100%"
          >
            <el-table-column prop="title" label="标题" min-width="180" show-overflow-tooltip />
            <el-table-column prop="level" label="等级" width="80">
              <template #default="{ row }">
                <span class="nb-chip" :class="levelChipMap[row.level] || 'nb-chip--neutral'">{{ levelText(row.level) }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="status" label="状态" width="90">
              <template #default="{ row }">
                <span class="status-text">{{ statusText(row.status) }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="reporter_name" label="上报人" width="100" />
            <el-table-column prop="project" label="项目" width="120" show-overflow-tooltip />
            <el-table-column prop="category" label="类别" width="100" show-overflow-tooltip />
            <el-table-column prop="created_at" label="上报时间" width="160">
              <template #default="{ row }">
                <span class="nb-mono">{{ formatTime(row.created_at) }}</span>
              </template>
            </el-table-column>
          </el-table>
        </div>

        <div class="records-pagination">
          <el-pagination
            v-model:current-page="page"
            :page-size="pageSize"
            :total="total"
            layout="total, prev, pager, next"
            @current-change="loadRecords"
          />
        </div>
      </section>

      <!-- 右栏：隐患详情与流转 -->
      <aside class="nb-panel report">
        <div class="nb-panel-head">
          <div class="nb-panel-title">隐患详情</div>
          <span
            v-if="recordDetail"
            class="nb-chip"
            :class="levelChipMap[recordDetail.level] || 'nb-chip--neutral'"
          >{{ levelText(recordDetail.level) }}</span>
        </div>
        <div class="report-body">
          <div v-if="!activeRecordId" class="nb-empty">
            <span>请选择一条隐患记录</span>
            <span class="empty-sub">点击左侧列表或表格行查看详情</span>
          </div>
          <template v-else-if="recordDetail">
            <div v-if="recordAnnotatedUrl" class="detail-image">
              <img :src="recordAnnotatedUrl" class="site-image" alt="隐患标注图" />
            </div>

            <div class="info-card">
              <div class="detail-row">
                <span class="detail-label">标题</span>
                <span class="detail-value">{{ recordDetail.title }}</span>
              </div>
              <div class="detail-row">
                <span class="detail-label">等级</span>
                <span class="detail-value">
                  <span class="nb-chip" :class="levelChipMap[recordDetail.level] || 'nb-chip--neutral'">
                    {{ levelText(recordDetail.level) }}
                  </span>
                </span>
              </div>
              <div class="detail-row">
                <span class="detail-label">状态</span>
                <span class="detail-value">{{ statusText(recordDetail.status) }}</span>
              </div>
              <div class="detail-row">
                <span class="detail-label">上报人</span>
                <span class="detail-value">{{ recordDetail.reporter?.name || '-' }}</span>
              </div>
              <div class="detail-row">
                <span class="detail-label">位置</span>
                <span class="detail-value">{{ recordDetail.location || '-' }}</span>
              </div>
              <div class="detail-row">
                <span class="detail-label">类别</span>
                <span class="detail-value">{{ recordDetail.category || '-' }}</span>
              </div>
              <div class="detail-row">
                <span class="detail-label">项目</span>
                <span class="detail-value">{{ recordDetail.project || '-' }}</span>
              </div>
              <div class="detail-row">
                <span class="detail-label">描述</span>
                <span class="detail-value text-wrap">{{ recordDetail.description || '-' }}</span>
              </div>
            </div>

            <div
              v-if="recordDetail.assignment?.deadline || recordDetail.timeline?.length"
              class="info-card"
            >
              <div class="sub-title">处置流转</div>
              <div v-if="recordDetail.assignment?.deadline" class="detail-row">
                <span class="detail-label">期限</span>
                <span class="detail-value nb-mono">
                  <el-icon><Timer /></el-icon>
                  {{ formatTime(recordDetail.assignment.deadline) }}
                </span>
              </div>
              <div v-if="recordDetail.timeline?.length" class="timeline">
                <div v-for="(node, i) in recordDetail.timeline" :key="i" class="tl-item">
                  <div class="tl-head">
                    <span>{{ timelineNodeMap[node.node] || node.node }}</span>
                    <span class="nb-mono">{{ formatTime(node.time).slice(5, 16) }}</span>
                  </div>
                  <div class="tl-note">{{ node.note || '—' }} · {{ node.operator || '系统' }}</div>
                </div>
              </div>
            </div>

            <div v-if="recordDets.length" class="dets-block">
              <div class="sub-title">AI 检测结果</div>
              <div v-for="(d, i) in recordDets" :key="i" class="det-card">
                <div class="det-head">
                  <span class="nb-chip" :class="riskChipMap[d.risk] || 'nb-chip--neutral'">
                    {{ riskText(d.risk) }} · 隐患 {{ i + 1 }}
                  </span>
                  <span class="conf nb-mono">置信度 {{ Math.round((d.conf || 0) * 100) }}%</span>
                </div>
                <div class="det-name">{{ d.label }}</div>
                <div v-if="d.note" class="det-row">
                  <span class="det-key">物理位置</span>
                  <span>{{ d.note }}</span>
                </div>
                <div v-if="d.fix" class="det-fix" :class="'fix-' + (d.risk || 'low')">
                  <span class="det-key">规范整改建议</span>
                  <span>{{ d.fix }}</span>
                </div>
              </div>
            </div>
          </template>
          <div v-else class="nb-empty">
            <span>加载中…</span>
          </div>
        </div>
      </aside>
    </div>

    <!-- 上报表单 -->
    <el-dialog v-model="reportDialogVisible" width="520px" append-to-body :show-close="false">
      <template #header>
        <div class="dialog-head">
          <div class="dialog-head-title">
            <span class="dialog-icon"><el-icon><Promotion /></el-icon></span>
            补全信息并上报处置单
          </div>
          <button type="button" class="dialog-close" @click="reportDialogVisible = false">
            <el-icon><Close /></el-icon>
          </button>
        </div>
      </template>
      <el-form ref="reportFormRef" :model="reportForm" :rules="reportRules" label-position="top" class="nb-form">
        <el-form-item label="隐患标题" prop="title">
          <el-input v-model="reportForm.title" placeholder="请输入隐患标题" />
        </el-form-item>
        <el-form-item label="隐患详细特征与处置要求" prop="description">
          <el-input v-model="reportForm.description" type="textarea" :rows="3" placeholder="请输入隐患描述" />
        </el-form-item>
        <div class="form-grid">
          <el-form-item label="工程施工部位 / 桩号" prop="location">
            <el-input v-model="reportForm.location" placeholder="请输入隐患位置" />
          </el-form-item>
          <el-form-item label="隐患类别" prop="category">
            <el-input v-model="reportForm.category" placeholder="请输入隐患类别" />
          </el-form-item>
        </div>
        <el-form-item label="所属项目" prop="project">
          <el-input v-model="reportForm.project" placeholder="请输入项目名称" />
        </el-form-item>
        <el-form-item label="评定风险等级" prop="level">
          <el-radio-group v-model="reportForm.level" class="risk-radio">
            <el-radio-button value="critical">重大</el-radio-button>
            <el-radio-button value="major">较大</el-radio-button>
            <el-radio-button value="general">一般</el-radio-button>
            <el-radio-button value="minor">轻微</el-radio-button>
          </el-radio-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <div class="dialog-footer">
          <el-button @click="reportDialogVisible = false">取消</el-button>
          <el-button type="primary" :loading="submitting" @click="onSubmitReport">提交上报</el-button>
        </div>
      </template>
    </el-dialog>

    <!-- 手动上报表单 -->
    <el-dialog v-model="manualDialogVisible" width="520px" append-to-body :show-close="false">
      <template #header>
        <div class="dialog-head">
          <div class="dialog-head-title">
            <span class="dialog-icon"><el-icon><DocumentAdd /></el-icon></span>
            手动上报隐患
          </div>
          <button type="button" class="dialog-close" @click="manualDialogVisible = false">
            <el-icon><Close /></el-icon>
          </button>
        </div>
      </template>
      <el-form ref="manualFormRef" :model="manualForm" :rules="manualRules" label-position="top" class="nb-form">
        <el-form-item label="隐患标题" prop="title">
          <el-input v-model="manualForm.title" placeholder="请输入隐患标题" />
        </el-form-item>
        <el-form-item label="隐患详细特征与处置要求" prop="description">
          <el-input v-model="manualForm.description" type="textarea" :rows="3" placeholder="请输入隐患描述" />
        </el-form-item>
        <div class="form-grid">
          <el-form-item label="工程施工部位 / 桩号" prop="location">
            <el-input v-model="manualForm.location" placeholder="请输入隐患位置" />
          </el-form-item>
          <el-form-item label="隐患类别" prop="category">
            <el-input v-model="manualForm.category" placeholder="请输入隐患类别" />
          </el-form-item>
          <el-form-item label="所属项目" prop="project">
            <el-input v-model="manualForm.project" placeholder="请输入项目名称" />
          </el-form-item>
          <el-form-item label="发生时间" prop="occurred_at">
            <el-date-picker
              v-model="manualForm.occurred_at"
              type="datetime"
              placeholder="选择日期时间"
              format="YYYY-MM-DD HH:mm:ss"
              value-format="YYYY-MM-DDTHH:mm:ss"
              style="width: 100%"
            />
          </el-form-item>
        </div>
        <el-form-item label="评定风险等级" prop="level">
          <el-radio-group v-model="manualForm.level" class="risk-radio">
            <el-radio-button value="critical">重大</el-radio-button>
            <el-radio-button value="major">较大</el-radio-button>
            <el-radio-button value="general">一般</el-radio-button>
            <el-radio-button value="minor">轻微</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="上传图片">
          <el-upload
            :auto-upload="false"
            :limit="9"
            accept="image/*"
            :file-list="manualFiles"
            :on-change="onManualFileChange"
            :on-remove="onManualFileRemove"
            list-type="picture"
          >
            <el-button type="primary" plain size="small">选择图片</el-button>
          </el-upload>
        </el-form-item>
      </el-form>
      <template #footer>
        <div class="dialog-footer">
          <el-button @click="manualDialogVisible = false">取消</el-button>
          <el-button type="primary" :loading="manualSubmitting" @click="onSubmitManual">提交上报</el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { Delete, Picture } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import type { UploadFile } from 'element-plus'
import { hazardApi } from '@/api'

// ===== Tab =====
const activeTab = ref('detect')

// ===== AI 识别 =====
const uploaded = ref(false)
const annotatedUrl = ref('')
const detecting = ref(false)
const activeHistoryId = ref('')
const detections = ref<any[]>([])
const historyList = ref<{ id: string; title: string; raw: any }[]>([])
const historySelectedIds = ref<string[]>([])
const uploadedFiles = ref<File[]>([])

// ===== 三栏工作台纯 UI 状态 =====
const historyKeyword = ref('')
const levelChipMap: Record<string, string> = {
  critical: 'nb-chip--danger',
  major: 'nb-chip--caution',
  general: 'nb-chip--info',
  minor: 'nb-chip--neutral',
}
const riskChipMap: Record<string, string> = {
  high: 'nb-chip--danger',
  medium: 'nb-chip--caution',
  low: 'nb-chip--info',
}
const timelineNodeMap: Record<string, string> = {
  reported: '上报',
  assigned: '派工',
  rectified: '整改反馈',
  reviewed: '验收',
  closed: '闭环',
  rejected: '驳回',
}
const filteredHistoryList = computed(() => {
  const kw = historyKeyword.value.trim().toLowerCase()
  if (!kw) return historyList.value
  return historyList.value.filter((h) => h.title.toLowerCase().includes(kw))
})
const topRisk = computed(() => {
  const risks = detections.value.map((d) => d.risk)
  return ['high', 'medium', 'low'].find((r) => risks.includes(r)) || ''
})
const topRiskText = computed(() => (topRisk.value ? riskText(topRisk.value) : '—'))
const avgConfText = computed(() => {
  if (!detections.value.length) return '—'
  const avg = detections.value.reduce((sum, d) => sum + (Number(d.conf) || 0), 0) / detections.value.length
  return `${Math.round(avg * 100)}%`
})

const reportDialogVisible = ref(false)
const submitting = ref(false)
const reportFormRef = ref<FormInstance>()
const reportForm = reactive({
  title: '',
  description: '',
  location: '',
  level: 'general',
  category: '',
  project: '',
})

const reportRules: FormRules = {
  title: [{ required: true, message: '请输入标题', trigger: 'blur' }],
  location: [{ required: true, message: '请输入位置', trigger: 'blur' }],
  category: [{ required: true, message: '请输入类别', trigger: 'blur' }],
  project: [{ required: true, message: '请输入项目', trigger: 'blur' }],
}

// ===== 隐患上报记录 =====
const recordsList = ref<{ id: string; title: string; status: string; level: string; reporter_name: string; project: string; category: string; created_at: string; raw: any }[]>([])
const recordsSelectedIds = ref<string[]>([])
const activeRecordId = ref('')
const recordDetail = ref<any>(null)
const recordDets = ref<any[]>([])
const recordAnnotatedUrl = ref('')
const filterStatus = ref('')
const filterLevel = ref('')
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)

// ===== 手动上报 =====
const manualDialogVisible = ref(false)
const manualSubmitting = ref(false)
const manualFormRef = ref<FormInstance>()
const manualFiles = ref<UploadFile[]>([])
const manualForm = reactive({
  title: '',
  description: '',
  location: '',
  level: 'general',
  category: '',
  project: '',
  occurred_at: '',
})

const manualRules: FormRules = {
  title: [{ required: true, message: '请输入标题', trigger: 'blur' }],
  location: [{ required: true, message: '请输入位置', trigger: 'blur' }],
  category: [{ required: true, message: '请输入类别', trigger: 'blur' }],
  project: [{ required: true, message: '请输入项目', trigger: 'blur' }],
  occurred_at: [{ required: true, message: '请选择发生时间', trigger: 'change' }],
}

function riskText(risk: string) {
  const map: Record<string, string> = { high: '高风险', medium: '中风险', low: '低风险' }
  return map[risk] || risk
}

function riskClass(risk: string) {
  return risk === 'high' ? 'tag-danger' : risk === 'medium' ? 'tag-warning' : 'tag-info'
}

function levelText(level: string) {
  const map: Record<string, string> = { critical: '重大', major: '较大', general: '一般', minor: '轻微' }
  return map[level] || level
}

function levelTagClass(level: string) {
  const map: Record<string, string> = { critical: 'tag-danger', major: 'tag-warning', general: 'tag-info', minor: '' }
  return map[level] || ''
}

function statusText(status: string) {
  const map: Record<string, string> = {
    pending: '待处理',
    processing: '处理中',
    pending_review: '待验收',
    closed: '已闭环',
    rejected: '已驳回',
  }
  return map[status] || status
}

function statusDotClass(status: string) {
  if (status === 'closed') return 'dot-green'
  if (status === 'rejected') return 'dot-red'
  return ''
}

function formatTime(ts: string) {
  if (!ts) return '-'
  return ts.replace('T', ' ').substring(0, 19)
}

async function loadHistory() {
  try {
    const res = await hazardApi.list({ page: 1, page_size: 20 })
    const items = res?.items || []
    historyList.value = items.map((h: any) => ({
      id: h.hazard_id,
      title: h.title,
      raw: h,
    }))
  } catch (e: any) {
    ElMessage.warning('历史记录加载失败，请稍后重试')
  }
}

async function onSelectHistory(item: { id: string; title: string; raw: any }) {
  activeHistoryId.value = item.id
  try {
    const detail = await hazardApi.detail(item.id)
    const media = detail?.media || {}
    // 优先显示标注图片，其次原始图片
    const annotated = media.annotated_images?.[0] || media.images?.[0]
    if (annotated) {
      annotatedUrl.value = annotated
      uploaded.value = true
    } else {
      uploaded.value = false
      annotatedUrl.value = ''
    }
    // 加载检测结果渲染分析报告
    detections.value = media.detections || []
  } catch {
    ElMessage.warning('隐患详情加载失败')
  }
}

async function onUpload(file: UploadFile) {
  if (!file.raw) return
  uploadedFiles.value = [file.raw]
  uploaded.value = true
  annotatedUrl.value = ''
  detections.value = []
  detecting.value = true
  try {
    const form = new FormData()
    form.append('images', file.raw)
    const res = await hazardApi.aiDetect(form)
    // 后端返回数组：每个元素含 original_url / annotated_url / detections
    const item = Array.isArray(res) ? res[0] : res
    annotatedUrl.value = item?.annotated_url || item?.original_url || ''
    detections.value = item?.detections || []
    if (!detections.value.length) {
      ElMessage.info('未识别到明显隐患')
    }
  } catch {
    ElMessage.warning('识别失败，请稍后重试')
    // 失败回退空态：否则图片区会永远停留在"图片加载中…"骨架
    uploaded.value = false
    annotatedUrl.value = ''
    detections.value = []
    uploadedFiles.value = []
  } finally {
    detecting.value = false
  }
}

function openReportDialog() {
  const first = detections.value[0]
  reportForm.title = first?.label || ''
  reportForm.description = detections.value.map((d) => d.label).join('、')
  reportForm.location = first?.note || ''
  reportDialogVisible.value = true
}

async function onSubmitReport() {
  await reportFormRef.value?.validate()
  submitting.value = true
  try {
    const form = new FormData()
    form.append('title', reportForm.title)
    form.append('description', reportForm.description)
    form.append('location', reportForm.location)
    form.append('level', reportForm.level)
    form.append('category', reportForm.category)
    form.append('project', reportForm.project)
    form.append('occurred_at', new Date().toISOString())
    uploadedFiles.value.forEach((f) => form.append('images', f))
    form.append('detections_json', JSON.stringify(detections.value))
    await hazardApi.submit(form)
    ElMessage.success('隐患已上报')
    reportDialogVisible.value = false
    uploaded.value = false
    uploadedFiles.value = []
    detections.value = []
    annotatedUrl.value = ''
    loadHistory()
  } catch {
    ElMessage.warning('上报失败，请稍后重试')
  } finally {
    submitting.value = false
  }
}

// ===== 隐患上报记录逻辑 =====
async function loadRecords() {
  try {
    const params: any = { page: page.value, page_size: pageSize.value }
    if (filterStatus.value) params.status = filterStatus.value
    if (filterLevel.value) params.level = filterLevel.value
    const res = await hazardApi.list(params)
    const items = res?.items || []
    total.value = res?.total || 0
    recordsList.value = items.map((h: any) => ({
      id: h.hazard_id,
      title: h.title,
      status: h.status,
      level: h.level,
      reporter_name: h.reporter_name || '',
      project: h.project || '',
      category: h.category || '',
      created_at: h.created_at || '',
      raw: h,
    }))
  } catch {
    ElMessage.warning('隐患记录加载失败，请稍后重试')
  }
}

async function onSelectRecord(item: any) {
  activeRecordId.value = item.id
  recordDetail.value = null
  recordDets.value = []
  recordAnnotatedUrl.value = ''
  try {
    const detail = await hazardApi.detail(item.id)
    recordDetail.value = detail
    recordDets.value = detail?.media?.detections || []
    recordAnnotatedUrl.value = detail?.media?.annotated_images?.[0] || detail?.media?.images?.[0] || ''
  } catch {
    ElMessage.warning('隐患详情加载失败')
  }
}

// ===== 手动上报逻辑 =====
function openManualReportDialog() {
  manualForm.title = ''
  manualForm.description = ''
  manualForm.location = ''
  manualForm.level = 'general'
  manualForm.category = ''
  manualForm.project = ''
  manualForm.occurred_at = ''
  manualFiles.value = []
  manualDialogVisible.value = true
}

function onManualFileChange(_file: UploadFile) {
  // handled by el-upload v-model
}

function onManualFileRemove(file: UploadFile) {
  const idx = manualFiles.value.indexOf(file)
  if (idx >= 0) manualFiles.value.splice(idx, 1)
}

async function onSubmitManual() {
  await manualFormRef.value?.validate()
  manualSubmitting.value = true
  try {
    const form = new FormData()
    form.append('title', manualForm.title)
    form.append('description', manualForm.description)
    form.append('location', manualForm.location)
    form.append('level', manualForm.level)
    form.append('category', manualForm.category)
    form.append('project', manualForm.project)
    form.append('occurred_at', manualForm.occurred_at)
    manualFiles.value.forEach((f) => {
      if (f.raw) form.append('images', f.raw)
    })
    await hazardApi.submit(form)
    ElMessage.success('隐患已上报')
    manualDialogVisible.value = false
    loadRecords()
    loadHistory()
  } catch {
    ElMessage.warning('上报失败，请稍后重试')
  } finally {
    manualSubmitting.value = false
  }
}

// ===== 删除逻辑 =====
function onToggleHistoryItem(id: string, checked: boolean) {
  if (checked) {
    historySelectedIds.value.push(id)
  } else {
    historySelectedIds.value = historySelectedIds.value.filter((x) => x !== id)
  }
}

function onToggleRecordsItem(id: string, checked: boolean) {
  if (checked) {
    recordsSelectedIds.value.push(id)
  } else {
    recordsSelectedIds.value = recordsSelectedIds.value.filter((x) => x !== id)
  }
}

async function onDeleteHistoryItem(id: string) {
  try {
    await ElMessageBox.confirm('确定删除该隐患记录？', '确认删除', { type: 'warning' })
  } catch { return }
  try {
    await hazardApi.delete(id)
    ElMessage.success('已删除')
    historySelectedIds.value = historySelectedIds.value.filter((x) => x !== id)
    if (activeHistoryId.value === id) {
      activeHistoryId.value = ''
      uploaded.value = false
      annotatedUrl.value = ''
      detections.value = []
    }
    loadHistory()
  } catch {
    ElMessage.warning('删除失败')
  }
}

async function onDeleteRecordsItem(id: string) {
  try {
    await ElMessageBox.confirm('确定删除该隐患记录？', '确认删除', { type: 'warning' })
  } catch { return }
  try {
    await hazardApi.delete(id)
    ElMessage.success('已删除')
    recordsSelectedIds.value = recordsSelectedIds.value.filter((x) => x !== id)
    if (activeRecordId.value === id) {
      activeRecordId.value = ''
      recordDetail.value = null
      recordDets.value = []
      recordAnnotatedUrl.value = ''
    }
    loadRecords()
    loadHistory()
  } catch {
    ElMessage.warning('删除失败')
  }
}

async function onBatchDeleteHistory() {
  try {
    await ElMessageBox.confirm(
      `确定删除选中的 ${historySelectedIds.value.length} 条隐患记录？`,
      '批量删除',
      { type: 'warning' }
    )
  } catch { return }
  let failed = 0
  for (const id of historySelectedIds.value) {
    try { await hazardApi.delete(id) } catch { failed++ }
  }
  ElMessage.success(`已删除 ${historySelectedIds.value.length - failed} 条` + (failed ? `，${failed} 条失败` : ''))
  historySelectedIds.value = []
  activeHistoryId.value = ''
  uploaded.value = false
  annotatedUrl.value = ''
  detections.value = []
  loadHistory()
}

async function onBatchDeleteRecords() {
  try {
    await ElMessageBox.confirm(
      `确定删除选中的 ${recordsSelectedIds.value.length} 条隐患记录？`,
      '批量删除',
      { type: 'warning' }
    )
  } catch { return }
  let failed = 0
  for (const id of recordsSelectedIds.value) {
    try { await hazardApi.delete(id) } catch { failed++ }
  }
  ElMessage.success(`已删除 ${recordsSelectedIds.value.length - failed} 条` + (failed ? `，${failed} 条失败` : ''))
  recordsSelectedIds.value = []
  activeRecordId.value = ''
  recordDetail.value = null
  recordDets.value = []
  recordAnnotatedUrl.value = ''
  loadRecords()
  loadHistory()
}

function onTabChange(tab: string) {
  if (tab === 'records') {
    loadRecords()
  }
}

onMounted(() => {
  loadHistory()
  if (activeTab.value === 'records') {
    loadRecords()
  }
})
</script>

<style scoped>
/* ===== 页面骨架：三栏各自独立滚动 ===== */
.hazard-page {
  gap: 14px;
  padding: 18px 20px 16px;
  min-height: 0;
  overflow: hidden;
}

.nb-page-head {
  flex: none;
  flex-wrap: wrap;
}

.head-left {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}

.head-icon {
  flex: none;
  width: 40px;
  height: 40px;
  display: grid;
  place-items: center;
  background: #ffffff;
  border: 2px solid #000;
  border-radius: var(--radius-card);
  box-shadow: var(--shadow-card);
  color: var(--primary);
}

.head-title-row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.head-sub {
  margin: 2px 0 0;
  font-size: 12px;
  color: var(--text-tertiary);
  line-height: 1.5;
}

/* 模式切换：胶囊分段控件 */
.mode-switch {
  flex: none;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 3px;
  background: #ffffff;
  border: 2px solid #000;
  border-radius: var(--radius-card);
  box-shadow: var(--shadow-card);
}

.mode-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 34px;
  padding: 0 14px;
  border: 2px solid transparent;
  border-radius: var(--radius-btn);
  background: transparent;
  color: var(--text-secondary);
  font-family: var(--font-mono);
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
  transition: all 0.2s ease;
}

.mode-btn:hover {
  background: var(--primary-light);
}

.mode-btn.active {
  background-image: var(--gradient-brand);
  color: #ffffff;
  border-color: #000;
  box-shadow: 2px 2px 0 #000;
}

.mode-count {
  padding: 0 5px;
  border: 1px solid rgba(0, 0, 0, 0.4);
  border-radius: var(--radius-tag);
  background: #EAEEFD;
  color: var(--text-primary);
  font-size: 10px;
  line-height: 1.6;
}

.mode-btn.active .mode-count {
  background: rgba(255, 255, 255, 0.25);
  border-color: rgba(255, 255, 255, 0.6);
  color: #ffffff;
}

.workspace-grid {
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: var(--history-width) minmax(0, 1fr) var(--panel-width);
  gap: 14px;
}

.rail,
.center,
.report {
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
}

/* ===== 左栏：巡检记录 ===== */
.rail .nb-panel-head {
  padding: 8px 10px;
  gap: 6px;
}

.count-chip {
  padding: 0 6px;
  border-radius: var(--radius-tag);
  background: #14171a;
  color: #ffffff;
  font-size: 10px;
  line-height: 1.7;
}

.mini-danger {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  padding: 2px 5px;
  border: 2px solid transparent;
  border-radius: var(--radius-btn);
  background: transparent;
  color: var(--danger-text);
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 700;
  white-space: nowrap;
  cursor: pointer;
  transition: all 0.2s ease;
}

.mini-danger:hover {
  border-color: #000;
  background: var(--danger-light);
}

.rail-search {
  flex: none;
  padding: 8px 10px;
  border-bottom: 2px solid #000;
  background: #ffffff;
}

.rail-list {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 8px;
}

.rail-card {
  position: relative;
  display: flex;
  align-items: flex-start;
  gap: 6px;
  padding: 9px 8px;
  border: 2px solid #000;
  border-radius: var(--radius-card);
  background: #ffffff;
  cursor: pointer;
  transition: all 0.2s ease;
}

.rail-card:hover {
  background: var(--page-bg);
  transform: translate(-3px, -3px);
  box-shadow: 7px 7px 0 #000;
}

.rail-card.active {
  background: linear-gradient(135deg, var(--primary-light), #EAEEFD);
  box-shadow: 3px 3px 0 #000;
}

.rail-check {
  flex: none;
  margin-top: 2px;
}

.rail-check.el-checkbox {
  height: auto;
  margin-right: 0;
}

.rail-check :deep(.el-checkbox__label) {
  display: none;
}

.rail-body {
  flex: 1;
  min-width: 0;
  cursor: pointer;
}

.rail-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
  margin-bottom: 4px;
}

.chip-dot {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: currentColor;
}

.rail-time {
  flex: none;
  font-size: 10px;
  font-weight: 700;
  color: var(--text-tertiary);
}

.rail-title {
  font-family: var(--font-headline);
  font-size: 13px;
  font-weight: 700;
  line-height: 1.4;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.rail-sub {
  margin-top: 2px;
  font-size: 11px;
  color: var(--text-tertiary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.rail-del {
  flex: none;
  width: 22px;
  height: 22px;
  display: grid;
  place-items: center;
  padding: 0;
  border: 1px solid transparent;
  border-radius: var(--radius-btn);
  background: transparent;
  color: var(--text-tertiary);
  cursor: pointer;
  opacity: 0;
  transition: all 0.2s ease;
}

.rail-card:hover .rail-del {
  opacity: 1;
}

.rail-del:hover {
  color: var(--danger-text);
  border-color: #000;
  background: var(--danger-light);
}

.rail-foot {
  flex: none;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 10px;
  border-top: 2px solid #000;
  background: var(--primary-light);
  font-size: 10px;
  color: var(--text-tertiary);
}

/* ===== 中栏：识别工作区 ===== */
.center-head {
  flex-wrap: wrap;
  gap: 6px;
}

.engine-chip {
  padding: 1px 6px;
  border-radius: var(--radius-tag);
  background: #14171a;
  color: #ffffff;
  font-size: 10px;
  font-weight: 700;
}

.stage {
  flex: 1;
  min-height: 260px;
  padding: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: #14171A;
  background-image: radial-gradient(rgba(255, 255, 255, 0.14) 1px, transparent 1px);
  background-size: 22px 22px;
  overflow: hidden;
}

.stage-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  text-align: center;
}

.stage-empty .el-icon {
  color: #657786;
}

.stage-empty-main {
  font-family: var(--font-headline);
  font-size: 15px;
  font-weight: 700;
  color: #F7F9FB;
}

.stage-empty-sub {
  font-size: 12px;
  color: #9aa4ae;
  margin-bottom: 4px;
}

.image-frame {
  position: relative;
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 2px solid #000;
  border-radius: var(--radius-card);
  background: #000000;
  overflow: hidden;
}

.site-image {
  width: 100%;
  height: 100%;
  object-fit: contain;
}

/* 加载态：品牌渐变圆环 */
.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 18px;
}

.loading-spinner {
  position: relative;
  width: 72px;
  height: 72px;
  border-radius: 50%;
  background: conic-gradient(from 0deg, #2f54eb, #7c3aed 40%, #c1ccf9 60%, #2f54eb 100%);
  -webkit-mask: radial-gradient(farthest-side, transparent calc(100% - 10px), #000 calc(100% - 9px));
  mask: radial-gradient(farthest-side, transparent calc(100% - 10px), #000 calc(100% - 9px));
  animation: loading-spin 0.9s linear infinite;
}

.loading-text {
  font-family: var(--font-mono);
  font-size: 12px;
  color: #E1E8ED;
  letter-spacing: 1px;
}

@keyframes loading-spin {
  to {
    transform: rotate(360deg);
  }
}

.hud {
  position: absolute;
  left: 10px;
  bottom: 10px;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 3px 8px;
  border: 2px solid #ffffff;
  border-radius: var(--radius-tag);
  background: rgba(0, 0, 0, 0.85);
  color: #ffffff;
  font-size: 10px;
}

.hud-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #22C55E;
  box-shadow: 0 0 0 2px rgba(16, 185, 129, 0.3);
}

.meta-strip {
  flex: none;
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 6px;
  padding: 10px 12px;
  background: var(--primary-light);
  border-top: 2px solid #000;
}

.meta-cell {
  min-width: 0;
  padding: 5px 7px;
  background: #ffffff;
  border: 2px solid #000;
  border-radius: var(--radius-input);
}

.meta-label {
  display: block;
  font-family: var(--font-mono);
  font-size: 9px;
  font-weight: 700;
  letter-spacing: 0.04em;
  color: var(--text-tertiary);
}

.meta-value {
  display: block;
  font-size: 12px;
  font-weight: 700;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* ===== 右栏：AI 分析报告 / 隐患详情 ===== */
.report-body {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 12px;
}

.empty-sub {
  font-size: 11px;
  color: var(--text-tertiary);
}

.overview {
  flex: none;
  padding: 9px 10px;
  background: var(--primary-light);
  border: 2px solid #000;
  border-radius: var(--radius-card);
}

.overview-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
  margin-bottom: 8px;
  font-size: 12px;
  font-weight: 700;
  color: var(--text-primary);
}

.overview-head .nb-mono {
  font-size: 10px;
  color: var(--primary);
}

.overview-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 6px;
}

.stat {
  min-width: 0;
  padding: 5px 4px;
  background: #ffffff;
  border: 1.5px solid #000;
  border-radius: var(--radius-input);
  text-align: center;
}

.stat-label {
  display: block;
  font-family: var(--font-mono);
  font-size: 9px;
  font-weight: 700;
  color: var(--text-tertiary);
  white-space: nowrap;
}

.stat-value {
  display: block;
  font-family: var(--font-headline);
  font-size: 14px;
  font-weight: 700;
  line-height: 1.3;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.stat-value.is-danger {
  color: var(--danger-text);
}

.det-card {
  flex: none;
  padding: 10px;
  background: #ffffff;
  border: 2px solid #000;
  border-radius: var(--radius-card);
  box-shadow: 3px 3px 0 #000;
}

.det-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
  flex-wrap: wrap;
  margin-bottom: 6px;
}

.conf {
  padding: 1px 5px;
  border: 1px solid rgba(0, 0, 0, 0.4);
  border-radius: var(--radius-tag);
  background: var(--primary-light);
  color: var(--text-primary);
  font-size: 10px;
  font-weight: 700;
  white-space: nowrap;
}

.det-name {
  margin-bottom: 6px;
  font-family: var(--font-headline);
  font-size: 13px;
  font-weight: 700;
  line-height: 1.35;
  color: var(--text-primary);
  word-break: break-word;
}

.det-row {
  display: flex;
  align-items: flex-start;
  gap: 4px;
  margin-bottom: 3px;
  font-size: 12px;
  line-height: 1.5;
  color: var(--text-secondary);
}

.det-key {
  flex: none;
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 700;
  color: var(--text-tertiary);
}

.det-fix {
  display: flex;
  flex-direction: column;
  gap: 3px;
  margin-top: 6px;
  padding: 6px 7px;
  border: 1px solid #000;
  border-radius: var(--radius-input);
  font-size: 12px;
  line-height: 1.5;
}

.fix-high {
  background: var(--danger-light);
  color: var(--danger-text);
}

.fix-medium {
  background: var(--caution-light);
  color: var(--caution-text);
}

.fix-low {
  background: var(--success-light);
  color: var(--success-text);
}

.btn-dispatch {
  flex: none;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  width: 100%;
  padding: 11px 12px;
  border: 3px solid #000;
  border-radius: var(--radius-card);
  background-image: var(--gradient-brand);
  color: #ffffff;
  font-family: var(--font-headline);
  font-size: 14px;
  font-weight: 700;
  cursor: pointer;
  box-shadow: var(--shadow-card);
  transition: all 0.2s ease;
}

.btn-dispatch:hover {
  transform: translate(-3px, -3px);
  box-shadow: 7px 7px 0 #000;
}

.btn-dispatch:active {
  transform: translate(2px, 2px);
  box-shadow: none;
}

/* ===== 中栏：上报记录表格 ===== */
.records-toolbar {
  flex: none;
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  padding: 10px 12px;
  border-bottom: 2px solid #000;
  background: #ffffff;
}

.records-table-wrap {
  flex: 1;
  min-height: 0;
  padding: 0 10px;
}

.records-pagination {
  flex: none;
  display: flex;
  justify-content: flex-end;
  padding: 8px 12px;
  border-top: 2px solid #000;
  background: #ffffff;
}

.status-text {
  font-size: 12px;
  color: var(--text-secondary);
}

/* ===== 右栏：隐患详情 ===== */
.detail-image {
  flex: none;
  border: 2px solid #000;
  border-radius: var(--radius-card);
  overflow: hidden;
  background: #14171A;
}

.detail-image .site-image {
  display: block;
  width: 100%;
  height: auto;
  max-height: 240px;
  object-fit: contain;
}

.info-card {
  flex: none;
  padding: 8px 10px;
  background: #ffffff;
  border: 2px solid #000;
  border-radius: var(--radius-card);
}

.detail-row {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 5px 0;
  border-bottom: 1px dashed var(--divider);
  font-size: 12px;
}

.detail-row:last-child {
  border-bottom: none;
}

.detail-label {
  flex: none;
  width: 48px;
  padding-top: 1px;
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 700;
  color: var(--text-tertiary);
}

.detail-value {
  flex: 1;
  min-width: 0;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  color: var(--text-primary);
  line-height: 1.5;
  word-break: break-all;
}

.detail-value.text-wrap {
  display: block;
  white-space: pre-wrap;
}

.sub-title {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 6px;
  font-family: var(--font-headline);
  font-size: 12px;
  font-weight: 700;
  color: var(--text-primary);
}

.sub-title::before {
  content: "";
  width: 3px;
  height: 12px;
  background: #000;
  flex: none;
}

.timeline {
  margin-left: 3px;
  padding-left: 12px;
  border-left: 2px solid #000;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.tl-item {
  position: relative;
}

.tl-item::before {
  content: "";
  position: absolute;
  left: -16px;
  top: 4px;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #000;
}

.tl-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
  font-size: 11px;
  font-weight: 700;
  color: var(--text-primary);
}

.tl-head .nb-mono {
  font-weight: 500;
  color: var(--text-tertiary);
}

.tl-note {
  margin-top: 1px;
  font-size: 11px;
  line-height: 1.45;
  color: var(--text-tertiary);
  word-break: break-word;
}

.dets-block {
  flex: none;
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding-top: 8px;
  border-top: 2px dashed rgba(0, 0, 0, 0.3);
}

/* ===== 弹窗 ===== */
.dialog-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin: -16px -20px;
  padding: 12px 14px;
  background-image: var(--gradient-brand);
  border-bottom: 3px solid #000;
  border-radius: 5px 5px 0 0;
}

.dialog-head-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-family: var(--font-headline);
  font-size: 15px;
  font-weight: 700;
  color: #ffffff;
}

.dialog-icon {
  flex: none;
  width: 26px;
  height: 26px;
  display: grid;
  place-items: center;
  background: #ffffff;
  border: 2px solid #000;
  border-radius: var(--radius-btn);
  color: var(--primary);
}

.dialog-close {
  flex: none;
  width: 24px;
  height: 24px;
  display: grid;
  place-items: center;
  padding: 0;
  background: #ffffff;
  border: 2px solid #000;
  border-radius: var(--radius-btn);
  color: #000000;
  cursor: pointer;
  transition: all 0.2s ease;
}

.dialog-close:hover {
  background: var(--danger-light);
}

.nb-form :deep(.el-form-item) {
  margin-bottom: 12px;
}

.nb-form :deep(.el-form-item__label) {
  padding-bottom: 4px;
  font-size: 12px;
  font-weight: 700;
  color: var(--text-primary);
  line-height: 1.4;
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.risk-radio {
  display: flex;
  gap: 6px;
  width: 100%;
}

.risk-radio :deep(.el-radio-button) {
  flex: 1;
}

.risk-radio :deep(.el-radio-button__inner) {
  width: 100%;
  padding: 6px 0;
  border: 2px solid #000;
  border-radius: var(--radius-btn);
  font-size: 12px;
  font-weight: 700;
  text-align: center;
}

.risk-radio :deep(.el-radio-button:not(:first-child) .el-radio-button__inner) {
  border-left: 2px solid #000;
}

.dialog-footer {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 10px;
}
</style>
