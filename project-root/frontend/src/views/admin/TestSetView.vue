<template>
  <div class="nb-page testset-page">
    <!-- 页头：标题 + 基准标签 + 主操作 -->
    <div class="nb-page-head testset-head">
      <div class="head-left">
        <div class="head-title-row">
          <span class="head-accent"></span>
          <h1 class="nb-title">测试集管理</h1>
          <span class="head-chip nb-mono">BENCHMARK LAB</span>
        </div>
        <p class="head-sub">管理视觉质检黄金基准图库与规程问答黄金评测集，确保生产模型精度基线可控可溯</p>
      </div>
      <div class="head-actions">
        <el-button :icon="Clock" @click="openHistory()">测试历史</el-button>
        <el-button :icon="VideoPlay" @click="openEvalAll">运行评测</el-button>
        <el-button type="primary" :icon="FolderAdd" @click="openCreate">新建测试集</el-button>
      </div>
    </div>

    <!-- 筛选面板 -->
    <div class="nb-panel filter-panel">
      <div class="filter-grid">
        <div class="field field-type">
          <label class="field-label">类型筛选</label>
          <el-select v-model="filterDraft.type" placeholder="全部类型">
            <el-option label="全部类型 (All Standard)" value="" />
            <el-option label="Vision 视觉标注集" value="vision" />
            <el-option label="Chat 规程问答集" value="chat" />
          </el-select>
        </div>
        <div class="field field-keyword">
          <label class="field-label">关键词检索</label>
          <el-input
            v-model="filterDraft.keyword"
            placeholder="检索测试集名称、描述或创建人..."
            clearable
            @keyup.enter="applyFilters"
            @clear="applyFilters"
          >
            <template #prefix>
              <el-icon><Search /></el-icon>
            </template>
          </el-input>
        </div>
        <div class="filter-actions">
          <el-button class="apply-btn" :icon="Search" @click="applyFilters">执行过滤</el-button>
          <el-button :icon="Refresh" @click="resetFilters">重置参数</el-button>
        </div>
      </div>

      <div class="filter-foot">
        <div class="stat-chips">
          <span class="stat-chip">
            <span class="stat-label">测试集总数</span>
            <strong class="nb-mono">{{ testSets.length }}</strong>
          </span>
          <span class="stat-chip">
            <span class="stat-label">Vision</span>
            <strong class="nb-mono">{{ typeCounts.vision }}</strong>
          </span>
          <span class="stat-chip">
            <span class="stat-label">Chat</span>
            <strong class="nb-mono">{{ typeCounts.chat }}</strong>
          </span>
        </div>
        <span class="foot-page nb-mono">
          匹配 {{ filteredTestSets.length }} 项 · 第 {{ safePage }} / {{ totalPages }} 页
        </span>
      </div>
    </div>

    <!-- 测试集表格 -->
    <div class="nb-panel table-panel">
      <div class="nb-panel-head">
        <span class="nb-panel-title">测试集列表</span>
        <span class="panel-meta nb-mono">DATASETS · {{ filteredTestSets.length }} ROWS</span>
      </div>

      <el-table
        :data="pagedTestSets"
        row-key="test_set_id"
        :row-class-name="rowClassName"
        class="set-table"
      >
        <el-table-column label="#" width="52" align="center">
          <template #default="{ $index }">
            <span class="nb-mono row-index">
              {{ String((safePage - 1) * listPageSize + $index + 1).padStart(2, '0') }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="测试集名称 / 描述" min-width="260">
          <template #default="{ row }">
            <div class="set-cell">
              <span class="set-name" :title="row.name">{{ row.name }}</span>
              <span class="set-desc nb-mono" :title="row.description || ''">
                {{ row.description || '未填写描述' }}
              </span>
              <button
                v-if="totalItemsOf(row) > 0"
                type="button"
                class="set-items-link nb-mono"
                @click="openItems(row)"
              >
                <el-icon><View /></el-icon>
                查看 {{ totalItemsOf(row) }} 条条目
              </button>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="类型" width="108">
          <template #default="{ row }">
            <span
              class="nb-chip type-chip"
              :class="row.model_type === 'chat' ? 'chip-chat' : 'chip-vision'"
            >
              <el-icon v-if="row.model_type !== 'chat'"><Picture /></el-icon>
              <el-icon v-else><ChatDotRound /></el-icon>
              {{ row.model_type }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="条目数" width="132" align="right">
          <template #default="{ row }">
            <span class="count-strong nb-mono">{{ itemCountText(row) }}</span>
            <span class="count-unit">{{ itemUnitText(row) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="创建人" width="140">
          <template #default="{ row }">
            <span class="creator-cell">
              <span class="creator-avatar">
                <el-icon><User /></el-icon>
              </span>
              <span class="creator-name nb-mono" :title="row.created_by">{{ row.created_by || '-' }}</span>
            </span>
          </template>
        </el-table-column>
        <el-table-column label="创建时间" width="130">
          <template #default="{ row }">
            <span class="cell-dim nb-mono nowrap">{{ fmtDate(row.created_at) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="300" align="right">
          <template #default="{ row }">
            <div class="row-actions">
              <el-button size="small" type="primary" :icon="VideoPlay" @click="openEvalFor(row)">
                运行评测
              </el-button>
              <el-button size="small" @click="openHistory(row)">历史</el-button>
              <button type="button" class="row-link" disabled title="编辑接口暂未开放">编辑</button>
              <button type="button" class="row-link row-link--danger" @click="onDelete(row.test_set_id)">
                删除
              </button>
            </div>
          </template>
        </el-table-column>
        <template #empty>
          <div class="nb-empty">暂无匹配的测试集，可调整筛选条件或新建测试集</div>
        </template>
      </el-table>

      <div class="table-foot">
        <div class="foot-info">
          <span>共 <strong class="nb-mono">{{ filteredTestSets.length }}</strong> 个测试集</span>
          <span class="foot-divider">|</span>
          <span>显示第 {{ listStart }} 至 {{ listEnd }} 条</span>
          <span class="foot-divider">|</span>
          <span class="size-box">
            每页
            <el-select v-model="listPageSize" class="page-size" size="small" @change="onPageSizeChange">
              <el-option :value="10" label="10 条" />
              <el-option :value="20" label="20 条" />
              <el-option :value="50" label="50 条" />
            </el-select>
          </span>
        </div>
        <el-pagination
          v-model:current-page="listPage"
          :page-size="listPageSize"
          :total="filteredTestSets.length"
          layout="prev, pager, next"
        />
      </div>
    </div>

    <!-- 新建测试集 -->
    <el-dialog v-model="dialogVisible" class="ts-dialog ts-create" width="520px" :show-close="false">
      <template #header>
        <div class="dlg-head dlg-head--plain">
          <div class="dlg-head-main">
            <span class="dlg-head-icon"><el-icon><Plus /></el-icon></span>
            <div class="dlg-head-text">
              <div class="dlg-head-title">新建测试集</div>
              <p class="dlg-head-sub nb-mono">CREATE BENCHMARK DATASET</p>
            </div>
          </div>
          <button type="button" class="dlg-close" aria-label="关闭" @click="dialogVisible = false">
            <el-icon><Close /></el-icon>
          </button>
        </div>
      </template>

      <div class="dlg-body create-body">
        <el-form ref="formRef" :model="form" label-position="top" class="create-form">
          <el-form-item label="测试集名称" required>
            <el-input v-model="form.name" maxlength="80" placeholder="如：视觉识别评测集-200" />
          </el-form-item>
          <el-form-item label="描述">
            <el-input
              v-model="form.description"
              type="textarea"
              :rows="3"
              placeholder="用途 / 覆盖场景 / 基线说明（可选）"
            />
          </el-form-item>
          <el-form-item label="基准类型">
            <el-radio-group v-model="form.model_type" class="type-radio">
              <el-radio value="vision">Vision 视觉标注</el-radio>
              <el-radio value="chat">Chat 规程问答</el-radio>
            </el-radio-group>
          </el-form-item>
          <template v-if="form.model_type === 'vision'">
            <el-form-item label="抽取数量">
              <el-input-number v-model="form.count" :min="10" :max="1000" :step="50" />
            </el-form-item>
            <div class="nb-note">
              <el-icon><InfoFilled /></el-icon>
              <p>
                创建后将自动从标注图片库（运营高速公路 / 隧道施工 / 简支梁 / 加油站）按比例抽样
                {{ form.count }} 张，并携带 YOLO 标注真值。
              </p>
            </div>
          </template>
        </el-form>
      </div>

      <template #footer>
        <div class="dlg-foot">
          <span class="foot-hint nb-mono">
            {{ form.model_type === 'vision' ? 'AUTO SAMPLING · YOLO GT' : 'QA PAIRS · EMPTY SET' }}
          </span>
          <div class="foot-btns">
            <el-button @click="dialogVisible = false">取消</el-button>
            <el-button type="primary" :loading="creating" @click="onCreate">创建</el-button>
          </div>
        </div>
      </template>
    </el-dialog>

    <!-- 测试集条目查看：vision 图片+标注 / chat 问答内容 -->
    <el-dialog v-model="itemsDialogVisible" class="ts-dialog ts-items" width="980px" top="5vh" :show-close="false">
      <template #header>
        <div class="dlg-head dlg-head--plain">
          <div class="dlg-head-main">
            <span class="dlg-head-icon"><el-icon><View /></el-icon></span>
            <div class="dlg-head-text">
              <div class="dlg-head-title" :title="`测试集条目 · ${currentSetName}`">
                测试集条目 · {{ currentSetName }}
                <span
                  class="nb-chip type-chip"
                  :class="currentSetType === 'chat' ? 'chip-chat' : 'chip-vision'"
                >{{ currentSetType }}</span>
              </div>
              <p class="dlg-head-sub nb-mono">DATASET ITEMS · {{ itemsTotal }} ROWS</p>
            </div>
          </div>
          <button type="button" class="dlg-close" aria-label="关闭" @click="itemsDialogVisible = false">
            <el-icon><Close /></el-icon>
          </button>
        </div>
      </template>

      <div class="dlg-body items-body">
        <div class="items-head">
          <span class="nb-mono">
            共 {{ itemsTotal }} 条{{ currentSetType === 'vision' ? '（含 YOLO 标注真值）' : '（问答评测）' }}
          </span>
          <el-pagination
            v-model:current-page="itemsPage"
            :page-size="itemsPageSize"
            :total="itemsTotal"
            layout="prev, pager, next"
            @current-change="loadItems"
          />
        </div>
        <!-- vision：图片网格 + 标注框可视化 -->
        <div v-if="currentSetType === 'vision'" v-loading="itemsLoading" class="items-grid">
          <div v-for="it in items" :key="it.id" class="item-card">
            <div class="img-wrap">
              <img :src="`/uploads/${it.image_path}`" loading="lazy" alt="" />
              <div
                v-for="(d, di) in it.detections"
                :key="di"
                class="det-box"
                :style="{
                  left: `${(d.cx - d.w / 2) * 100}%`,
                  top: `${(d.cy - d.h / 2) * 100}%`,
                  width: `${d.w * 100}%`,
                  height: `${d.h * 100}%`,
                }"
              ><span class="det-label">{{ d.name_zh }}</span></div>
            </div>
            <div class="item-meta">
              <span class="item-src">{{ it.source }}</span>
              <span class="item-count nb-mono">{{ it.detections.length }} 个标注</span>
            </div>
          </div>
        </div>
        <!-- chat：问答列表 -->
        <div v-else v-loading="itemsLoading" class="qa-list">
          <div v-for="it in items" :key="it.id" class="qa-card">
            <div class="qa-q"><span class="qa-tag">问</span>{{ it.query }}</div>
            <div class="qa-a"><span class="qa-tag qa-tag-a">答</span>{{ it.expected_answer }}</div>
          </div>
        </div>
      </div>
    </el-dialog>

    <!-- 运行评测：选被测模型 → 按类型联动测试集与辅助模型 -->
    <el-dialog v-model="testModelVisible" class="ts-dialog ts-eval" width="560px" :show-close="false" @closed="evalTargetSet = null">
      <template #header>
        <div class="dlg-head dlg-head--brand">
          <div class="dlg-head-main">
            <span class="dlg-head-icon"><el-icon><VideoPlay /></el-icon></span>
            <div class="dlg-head-text">
              <div class="dlg-head-title">
                运行模型评测
                <span class="dlg-head-en nb-mono">BENCHMARK EVALUATION</span>
              </div>
              <p class="dlg-head-sub nb-mono">MODEL × DATASET · ASYNC DISPATCH</p>
            </div>
          </div>
          <button type="button" class="dlg-close" aria-label="关闭" @click="testModelVisible = false">
            <el-icon><Close /></el-icon>
          </button>
        </div>
      </template>

      <div class="dlg-body eval-body">
        <!-- 测试集概况条 -->
        <div class="target-card">
          <div class="target-label nb-mono">SELECTED TARGET DATASET</div>
          <template v-if="selectedEvalSet">
            <div class="target-name" :title="selectedEvalSet.name">{{ selectedEvalSet.name }}</div>
            <div class="target-meta">
              <span
                class="nb-chip type-chip"
                :class="selectedEvalSet.model_type === 'chat' ? 'chip-chat' : 'chip-vision'"
              >{{ selectedEvalSet.model_type }}</span>
              <span class="target-count nb-mono">
                {{ itemCountText(selectedEvalSet) }} {{ itemUnitText(selectedEvalSet) }}
              </span>
            </div>
          </template>
          <div v-else class="target-empty">
            尚未选择测试集 —— 先选择被测模型，即可从同类型测试集中选定评测目标
          </div>
        </div>

        <el-form
          ref="testFormRef"
          :model="testForm"
          :rules="testRules"
          label-position="top"
          class="eval-form"
        >
          <el-form-item prop="model_config_id">
            <template #label>
              <span class="form-label">
                {{ mainModelType === 'chat' ? '① 被测对话模型 (Chat LLM)' : '被测模型' }}
                <span v-if="mainModelType === 'chat'" class="label-chip nb-mono">GENERATOR</span>
              </span>
            </template>
            <el-select
              v-model="testForm.model_config_id"
              placeholder="选择要评测的模型"
              style="width: 100%"
              @change="onEvalModelChange"
            >
              <el-option-group label="视觉模型（vision）">
                <el-option v-for="m in modelsByType.vision" :key="m.id" :label="m.model_name" :value="m.id" />
              </el-option-group>
              <el-option-group label="对话模型（chat）">
                <el-option v-for="m in modelsByType.chat" :key="m.id" :label="m.model_name" :value="m.id" />
              </el-option-group>
            </el-select>
          </el-form-item>

          <el-form-item label="测试集" prop="test_set_id">
            <el-select
              v-model="testForm.test_set_id"
              :placeholder="filteredSets.length ? '选择测试集' : '没有可用测试集'"
              :disabled="!mainModelType"
              style="width: 100%"
            >
              <el-option
                v-for="t in filteredSets"
                :key="t.test_set_id"
                :label="`${t.name}（${t.model_type}${t.image_count ? ` · ${t.image_count}图` : ''}${t.question_count ? ` · ${t.question_count}题` : ''}）`"
                :value="t.test_set_id"
              />
            </el-select>
          </el-form-item>

          <template v-if="mainModelType === 'chat'">
            <el-form-item prop="embedding_model_id">
              <template #label>
                <span class="form-label">② 检索向量模型 (Embedding)<span class="label-chip nb-mono">RETRIEVAL</span></span>
              </template>
              <el-select v-model="testForm.embedding_model_id" placeholder="检索向量化模型" style="width: 100%">
                <el-option v-for="m in modelsByType.embedding" :key="m.id" :label="m.model_name" :value="m.id" />
              </el-select>
            </el-form-item>
            <el-form-item prop="crossencoder_model_id">
              <template #label>
                <span class="form-label">③ 重排模型 (CrossEncoder Rerank)<span class="label-chip nb-mono">RERANKER</span></span>
              </template>
              <el-select v-model="testForm.crossencoder_model_id" placeholder="检索重排序模型" style="width: 100%">
                <el-option v-for="m in modelsByType.rerank" :key="m.id" :label="m.model_name" :value="m.id" />
              </el-select>
            </el-form-item>
            <div class="nb-note">
              <el-icon><InfoFilled /></el-icon>
              <p>chat 评测将使用所选 Embedding + CrossEncoder 构建检索增强问答，计算 recall@5 / MRR 与回答准确率。</p>
            </div>
          </template>
          <div v-else-if="mainModelType === 'vision'" class="nb-note">
            <el-icon><InfoFilled /></el-icon>
            <p>vision 评测将逐图调用模型识别，与 YOLO 真值按类别 + IoU≥0.5 匹配，计算 precision / recall / F1。</p>
          </div>
        </el-form>
      </div>

      <template #footer>
        <div class="dlg-foot">
          <span class="foot-hint nb-mono">ASYNC EVALUATION · CHECK HISTORY FOR RESULT</span>
          <div class="foot-btns">
            <el-button @click="testModelVisible = false">取消</el-button>
            <el-button type="primary" :loading="running" @click="onRunTest">开始评测</el-button>
          </div>
        </div>
      </template>
    </el-dialog>

    <!-- 测试历史：点击行首箭头展开详情（运行时间 / token 消耗 / 评估指标） -->
    <el-dialog v-model="historyVisible" class="ts-dialog ts-history" width="940px" top="5vh" :show-close="false">
      <template #header>
        <div class="dlg-head dlg-head--dark">
          <div class="dlg-head-main">
            <span class="hist-dot"></span>
            <div class="dlg-head-text">
              <div class="dlg-head-title">{{ historyTitle }}</div>
              <p class="dlg-head-sub nb-mono">HISTORY AUDIT BENCHMARK LEDGER</p>
            </div>
          </div>
          <button type="button" class="dlg-close" aria-label="关闭" @click="historyVisible = false">
            <el-icon><Close /></el-icon>
          </button>
        </div>
      </template>

      <div class="dlg-body history-body">
        <div class="history-head">
          <span class="nb-mono">RECENT {{ historyList.length }} RUNS · 点击行左侧箭头展开运行明细</span>
          <el-button size="small" :icon="Refresh" @click="loadHistory">刷新</el-button>
        </div>

        <el-table
          :data="historyList"
          class="history-table"
          :empty-text="historyEmptyText"
          :row-class-name="historyRowClassName"
        >
          <el-table-column type="expand">
            <template #default="{ row }">
              <div class="history-detail">
                <el-descriptions :column="3" border size="small" title="运行信息">
                  <el-descriptions-item label="运行时间">{{ fmtTime(row.executed_at) }}</el-descriptions-item>
                  <el-descriptions-item label="总耗时">{{ fmtDuration(detailOf(row).duration_s) }}</el-descriptions-item>
                  <el-descriptions-item label="执行人">{{ row.executed_by }}</el-descriptions-item>
                </el-descriptions>
                <el-descriptions :column="3" border size="small" title="Token 消耗" class="mt8">
                  <el-descriptions-item label="输入 prompt">
                    {{ detailOf(row).tokens?.prompt_tokens?.toLocaleString?.() ?? '未记录' }}
                  </el-descriptions-item>
                  <el-descriptions-item label="输出 completion">
                    {{ detailOf(row).tokens?.completion_tokens?.toLocaleString?.() ?? '未记录' }}
                  </el-descriptions-item>
                  <el-descriptions-item label="合计 total">
                    {{ detailOf(row).tokens?.total_tokens?.toLocaleString?.() ?? '未记录' }}
                  </el-descriptions-item>
                </el-descriptions>
                <el-descriptions :column="4" border size="small" title="评估指标" class="mt8">
                  <el-descriptions-item label="条目数">{{ row.total_items }}</el-descriptions-item>
                  <el-descriptions-item label="正确/命中 TP">{{ row.correct_items }}</el-descriptions-item>
                  <el-descriptions-item label="准确率">{{ pct(row.accuracy) }}</el-descriptions-item>
                  <el-descriptions-item v-if="row.model_type === 'vision'" label="精确率 P">{{ pct(row.precision_val) }}</el-descriptions-item>
                  <el-descriptions-item v-if="row.model_type === 'vision'" label="召回率 R">{{ pct(row.recall_val) }}</el-descriptions-item>
                  <el-descriptions-item v-if="row.model_type === 'vision'" label="F1">{{ num(row.f1_score) }}</el-descriptions-item>
                  <el-descriptions-item v-if="row.model_type === 'vision'" label="TP/FP/FN">
                    {{ detailOf(row).tp ?? '-' }} / {{ detailOf(row).fp ?? '-' }} / {{ detailOf(row).fn ?? '-' }}
                  </el-descriptions-item>
                  <el-descriptions-item v-if="row.model_type === 'chat'" label="检索 Recall@5">{{ pct(row.recall_val) }}</el-descriptions-item>
                  <el-descriptions-item v-if="row.model_type === 'chat'" label="MRR">{{ num(detailOf(row).mrr) }}</el-descriptions-item>
                  <el-descriptions-item label="平均延迟">{{ Math.round(row.avg_latency_ms || 0) }} ms</el-descriptions-item>
                </el-descriptions>
                <div v-if="detailOf(row).status === 'failed'" class="history-error">
                  失败原因：{{ detailOf(row).error || '未知' }}
                </div>
                <div v-if="detailOf(row).items?.length" class="history-items">
                  <div class="history-items-title">逐条明细（前 10 条，共 {{ detailOf(row).items.length }} 条）</div>
                  <div v-for="it in detailOf(row).items.slice(0, 10)" :key="it.item_id" class="history-item-line">
                    <template v-if="row.model_type === 'vision'">
                      <span class="ellipsis">{{ it.image_path }}</span>
                      <span>真值 {{ it.gt_count }} / 预测 {{ it.pred_count }} · TP{{ it.tp }} FP{{ it.fp }} FN{{ it.fn }}</span>
                      <span v-if="it.error" class="err-text">{{ it.error }}</span>
                    </template>
                    <template v-else>
                      <span class="ellipsis">{{ it.query }}</span>
                      <span>R@5 {{ it.recall_at_5 }} · 相似度 {{ it.similarity }} · {{ it.correct ? '正确' : '错误' }}</span>
                      <span v-if="it.error" class="err-text">{{ it.error }}</span>
                    </template>
                  </div>
                </div>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="执行时间" width="142">
            <template #default="{ row }">
              <span class="nb-mono cell-dim nowrap">{{ fmtTime(row.executed_at) }}</span>
            </template>
          </el-table-column>
          <el-table-column v-if="!historySetId" prop="test_set_name" label="测试集" min-width="130">
            <template #default="{ row }">
              <span class="hist-set-name" :title="row.test_set_name">{{ row.test_set_name || '-' }}</span>
            </template>
          </el-table-column>
          <el-table-column label="被测模型 / 链路配置" min-width="150">
            <template #default="{ row }">
              <div class="model-name" :title="row.model_name">{{ row.model_name || '-' }}</div>
              <div class="model-sub nb-mono">
                {{ row.model_type === 'vision' ? 'IoU ≥ 0.5 · YOLO 真值' : 'RAG 检索链路 · Top-K 5' }}
              </div>
            </template>
          </el-table-column>
          <el-table-column label="核心指标 (Metrics)" min-width="156">
            <template #default="{ row }">
              <div v-if="detailOf(row).status === 'running'" class="metric-running nb-mono">运行计算中...</div>
              <template v-else-if="row.model_type === 'vision'">
                <div class="metric-main nb-mono">F1: {{ num(row.f1_score) }}</div>
                <div class="metric-sub nb-mono">P {{ pct(row.precision_val) }} / R {{ pct(row.recall_val) }}</div>
              </template>
              <template v-else>
                <div class="metric-main metric-main--accent nb-mono">MRR: {{ num(detailOf(row).mrr) }}</div>
                <div class="metric-sub nb-mono">Recall@5: {{ pct(row.recall_val) }}</div>
              </template>
            </template>
          </el-table-column>
          <el-table-column label="条目数" width="74" align="right">
            <template #default="{ row }">
              <span class="nb-mono cell-strong">{{ row.total_items }}</span>
            </template>
          </el-table-column>
          <el-table-column label="耗时" width="84">
            <template #default="{ row }">
              <span class="nb-mono cell-dim">{{ fmtDuration(detailOf(row).duration_s) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="状态" width="98" align="right">
            <template #default="{ row }">
              <span class="nb-chip status-chip" :class="statusChip(detailOf(row).status)">
                <span v-if="detailOf(row).status === 'running'" class="chip-spin"></span>
                <span v-else class="chip-dot"></span>
                {{ statusText(detailOf(row).status) }}
              </span>
            </template>
          </el-table-column>
        </el-table>

        <div class="hist-foot-note">
          <span class="hist-note-text">
            评测结果与逐条明细统一存档于测试结果库，可在行内展开查看 token 消耗与逐条命中情况。
          </span>
          <button type="button" class="ghost-btn" disabled title="导出接口暂未开放">
            <el-icon><Download /></el-icon>
            导出明细 CSV
          </button>
        </div>
      </div>

      <template #footer>
        <div class="dlg-foot">
          <span class="foot-hint nb-mono">AUDIT TRAIL · {{ historyList.length }} RECORDS</span>
          <div class="foot-btns">
            <el-button class="dark-btn" @click="historyVisible = false">关闭窗口</el-button>
          </div>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import {
  Search,
  Refresh,
  Plus,
  FolderAdd,
  VideoPlay,
  Clock,
  View,
  User,
  Close,
  InfoFilled,
  Picture,
  ChatDotRound,
  Download,
} from '@element-plus/icons-vue'
import http from '@/api/http'

const testSets = ref<any[]>([])
const dialogVisible = ref(false)
const creating = ref(false)
const form = ref({ name: '', description: '', model_type: 'vision', count: 200 })

// 条目查看状态
const itemsDialogVisible = ref(false)
const itemsLoading = ref(false)
const items = ref<any[]>([])
const itemsTotal = ref(0)
const itemsPage = ref(1)
const itemsPageSize = 12
const currentSetName = ref('')
const currentSetId = ref('')
const currentSetType = ref('')

// 测试模型状态
const testModelVisible = ref(false)
const running = ref(false)
const testFormRef = ref<FormInstance>()
const models = ref<any[]>([])
const testForm = ref({
  model_config_id: undefined as number | undefined,
  test_set_id: '',
  embedding_model_id: undefined as number | undefined,
  crossencoder_model_id: undefined as number | undefined,
})

// 模型按类型分组（被测仅 vision/chat，辅助为 embedding/rerank）
const modelsByType = computed(() => {
  const pick = (t: string) => models.value.filter((m) => m.model_type === t)
  return { vision: pick('vision'), chat: pick('chat'), embedding: pick('embedding'), rerank: pick('rerank') }
})

// 被测模型类型（驱动测试集过滤与辅助模型显隐）
const mainModelType = computed(
  () => models.value.find((m) => m.id === testForm.value.model_config_id)?.model_type || '',
)

// 测试集仅显示与被测模型同类型者
const filteredSets = computed(() =>
  mainModelType.value ? testSets.value.filter((t) => t.model_type === mainModelType.value) : [],
)

const testRules: FormRules = {
  model_config_id: [{ required: true, message: '请选择被测模型', trigger: 'change' }],
  test_set_id: [{ required: true, message: '请选择测试集', trigger: 'change' }],
  embedding_model_id: [{ required: true, message: 'chat 评测必须选择 embedding 模型', trigger: 'change' }],
  crossencoder_model_id: [{ required: true, message: 'chat 评测必须选择 crossencoder 模型', trigger: 'change' }],
}

async function loadModels() {
  try {
    const res: any = await http.get('/admin/models')
    models.value = Array.isArray(res) ? res : []
  } catch { ElMessage.warning('模型列表加载失败') }
}

function openTestModel() {
  testForm.value = { model_config_id: undefined, test_set_id: '', embedding_model_id: undefined, crossencoder_model_id: undefined }
  testModelVisible.value = true
  loadModels()
}

// UI-only：行内发起评测时记录目标测试集，选定同类型模型后自动回填
const evalTargetSet = ref<{ test_set_id: string; name: string; model_type: string } | null>(null)

function openEvalAll() {
  evalTargetSet.value = null
  openTestModel()
}

function openEvalFor(row: any) {
  evalTargetSet.value = {
    test_set_id: row.test_set_id,
    name: row.name,
    model_type: row.model_type,
  }
  openTestModel()
}

function onEvalModelChange() {
  onMainModelChange()
  if (evalTargetSet.value && evalTargetSet.value.model_type === mainModelType.value) {
    testForm.value.test_set_id = evalTargetSet.value.test_set_id
  }
}

function onMainModelChange() {
  // 切换被测模型类型时清空测试集与辅助模型，避免残留不匹配的选中
  testForm.value.test_set_id = ''
  testForm.value.embedding_model_id = undefined
  testForm.value.crossencoder_model_id = undefined
  testFormRef.value?.clearValidate()
}

async function onRunTest() {
  await testFormRef.value?.validate()
  running.value = true
  try {
    // chat 与 vision 走不同接口，各自只提交自己需要的参数
    const isChat = mainModelType.value === 'chat'
    const url = `/admin/test-sets/${testForm.value.test_set_id}${isChat ? '/run-chat' : '/run-vision'}`
    const body = isChat
      ? {
          model_config_id: testForm.value.model_config_id,
          embedding_model_id: testForm.value.embedding_model_id,
          crossencoder_model_id: testForm.value.crossencoder_model_id,
        }
      : { model_config_id: testForm.value.model_config_id }
    await http.post(url, body)
    ElMessage.success('测试已启动，可在测试历史中查看进度与结果')
    testModelVisible.value = false
  } catch { /* 拦截器已提示后端错误（类型不匹配/缺少辅助模型等） */ }
  finally { running.value = false }
}

// ---------- 测试历史 ----------
const historyVisible = ref(false)
const historyList = ref<any[]>([])
// 有值时只看该测试集的记录，为空表示全部
const historySetId = ref('')
const historySetName = ref('')

const historyTitle = computed(() =>
  historySetName.value ? `测试历史 · ${historySetName.value}` : '测试历史',
)
const historyEmptyText = computed(() =>
  historySetId.value ? '该测试集暂无评测记录' : '暂无评测记录',
)

// detail_json 解析缓存（同一行多次渲染只解析一次）
const detailCache = new Map<string, any>()

function detailOf(row: any): any {
  if (!detailCache.has(row.result_id)) {
    try { detailCache.set(row.result_id, JSON.parse(row.detail_json || '{}')) }
    catch { detailCache.set(row.result_id, {}) }
  }
  return detailCache.get(row.result_id)
}

function openHistory(row?: any) {
  historySetId.value = row?.test_set_id || ''
  historySetName.value = row?.name || ''
  historyVisible.value = true
  loadHistory()
}

async function loadHistory() {
  try {
    const query = historySetId.value ? `?test_set_id=${historySetId.value}` : ''
    const res: any = await http.get(`/admin/test-results${query}`)
    historyList.value = Array.isArray(res) ? res : []
    detailCache.clear()
  } catch { ElMessage.warning('测试历史加载失败') }
}

// 格式化：ISO 时间 → 本地可读
function fmtTime(iso: string): string {
  if (!iso) return '-'
  const d = new Date(iso)
  return isNaN(d.getTime()) ? iso : d.toLocaleString('zh-CN', { hour12: false })
}

function fmtDuration(s: unknown): string {
  if (s == null) return '未记录'
  const sec = Number(s)
  if (sec >= 60) return `${Math.floor(sec / 60)} 分 ${Math.round(sec % 60)} 秒`
  return `${sec.toFixed(1)} 秒`
}

function pct(v: unknown): string {
  return v == null ? '-' : `${(Number(v) * 100).toFixed(1)}%`
}

function num(v: unknown): string {
  return v == null ? '-' : Number(v).toFixed(3)
}

function statusText(s: string): string {
  return { running: '运行中', done: '已完成', failed: '失败', queued: '排队中', pending: '排队中' }[s] || '未知'
}

function statusTag(s: string): string {
  return { running: 'warning', done: 'success', failed: 'danger' }[s] || 'info'
}

async function load() {
  try {
    // http 拦截器已解包为 data，res 即列表本身
    const res = await http.get('/admin/test-sets')
    testSets.value = Array.isArray(res) ? res : []
    // UI-only：数据量变化后把页码收敛到有效范围
    const maxPage = Math.max(1, Math.ceil(filteredTestSets.value.length / listPageSize.value))
    if (listPage.value > maxPage) listPage.value = maxPage
  } catch { ElMessage.warning('加载失败') }
}

function openCreate() {
  form.value = { name: '', description: '', model_type: 'vision', count: 200 }
  dialogVisible.value = true
}

async function onCreate() {
  if (!form.value.name.trim()) { ElMessage.warning('请输入名称'); return }
  creating.value = true
  const fd = new FormData()
  fd.append('name', form.value.name)
  fd.append('description', form.value.description)
  fd.append('model_type', form.value.model_type)
  fd.append('count', String(form.value.count))
  try {
    const res: any = await http.post('/admin/test-sets', fd)
    const cnt = res?.image_count
    ElMessage.success(cnt != null ? `创建成功，已从标注图片库抽取 ${cnt} 张带标注图片` : '创建成功')
    dialogVisible.value = false
    load()
  } catch { ElMessage.warning('创建失败') }
  finally { creating.value = false }
}

async function onDelete(id: string) {
  try { await ElMessageBox.confirm('删除测试集将同时清除其图片与标注条目，确定？', '确认', { type: 'warning' }) } catch { return }
  try {
    await http.delete(`/admin/test-sets/${id}`)
    ElMessage.success('已删除')
    load()
  } catch { ElMessage.warning('删除失败') }
}

function openItems(row: any) {
  currentSetName.value = row.name
  currentSetId.value = row.test_set_id
  currentSetType.value = row.model_type
  itemsPage.value = 1
  itemsDialogVisible.value = true
  loadItems()
}

async function loadItems() {
  itemsLoading.value = true
  try {
    const res: any = await http.get(`/admin/test-sets/${currentSetId.value}/items`, {
      params: { page: itemsPage.value, page_size: itemsPageSize },
    })
    items.value = res?.items || []
    itemsTotal.value = res?.total || 0
  } catch { ElMessage.warning('条目加载失败') }
  finally { itemsLoading.value = false }
}

// ---------- 列表筛选 / 分页（纯展示层状态，不改动接口与数据结构） ----------
const filterDraft = reactive({ type: '', keyword: '' })
const appliedFilter = reactive({ type: '', keyword: '' })
const listPage = ref(1)
const listPageSize = ref(10)

// 客户端筛选仅作用于已加载的测试集列表
const filteredTestSets = computed(() => {
  const kw = appliedFilter.keyword.trim().toLowerCase()
  return testSets.value.filter((t) => {
    const typeOk = !appliedFilter.type || t.model_type === appliedFilter.type
    const text = `${t.name || ''} ${t.description || ''} ${t.created_by || ''}`.toLowerCase()
    return typeOk && (!kw || text.includes(kw))
  })
})

const typeCounts = computed(() => ({
  vision: testSets.value.filter((t) => t.model_type === 'vision').length,
  chat: testSets.value.filter((t) => t.model_type === 'chat').length,
}))

const totalPages = computed(() =>
  Math.max(1, Math.ceil(filteredTestSets.value.length / listPageSize.value)),
)
const safePage = computed(() => Math.min(listPage.value, totalPages.value))
const pagedTestSets = computed(() => {
  const start = (safePage.value - 1) * listPageSize.value
  return filteredTestSets.value.slice(start, start + listPageSize.value)
})
const listStart = computed(() =>
  filteredTestSets.value.length ? (safePage.value - 1) * listPageSize.value + 1 : 0,
)
const listEnd = computed(() =>
  Math.min(safePage.value * listPageSize.value, filteredTestSets.value.length),
)

function applyFilters() {
  appliedFilter.type = filterDraft.type
  appliedFilter.keyword = filterDraft.keyword
  listPage.value = 1
}

function resetFilters() {
  filterDraft.type = ''
  filterDraft.keyword = ''
  applyFilters()
}

function onPageSizeChange() {
  listPage.value = 1
}

function rowClassName({ row }: { row: any; rowIndex: number }): string {
  return row.model_type === 'chat' ? 'row-chat' : 'row-vision'
}

function historyRowClassName({ row }: { row: any; rowIndex: number }): string {
  return detailOf(row).status === 'running' ? 'hist-row-running' : ''
}

// 列表展示辅助：仅格式化，不改动数据
function fmtDate(v: string): string {
  if (!v) return '-'
  return String(v).replace('T', ' ').slice(0, 16)
}

function totalItemsOf(row: any): number {
  return (row.image_count || 0) + (row.question_count || 0)
}

function itemCountText(row: any): string {
  return row.model_type === 'chat' ? `${row.question_count || 0}` : `${row.image_count || 0}`
}

function itemUnitText(row: any): string {
  return row.model_type === 'chat' ? '道标准问答' : '张标注图'
}

// 运行评测弹窗概况条：跟随当前所选测试集
const selectedEvalSet = computed(
  () => testSets.value.find((t) => t.test_set_id === testForm.value.test_set_id) || null,
)

function statusChip(s: string): string {
  return {
    running: 'nb-chip--info',
    done: 'nb-chip--normal',
    failed: 'nb-chip--danger',
  }[s] || 'nb-chip--neutral'
}

onMounted(load)
</script>

<style scoped>
.testset-page {
  align-items: stretch;
}

/* ---------- 页头 ---------- */
.head-left {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
}
.head-title-row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
.head-accent {
  width: 6px;
  height: 24px;
  flex: none;
  border: 2px solid #000;
  border-radius: 2px;
  background: #000;
}
.head-chip {
  padding: 1px 8px;
  border: 1.5px solid #000;
  border-radius: var(--radius-tag);
  background: #000;
  color: #fff;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}
.head-sub {
  margin: 0;
  font-size: 13px;
  color: var(--text-tertiary);
}
.head-actions {
  display: flex;
  gap: 10px;
  flex: none;
  flex-wrap: wrap;
}

/* ---------- 筛选面板 ---------- */
.filter-panel {
  padding: 14px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.filter-grid {
  display: grid;
  grid-template-columns: 230px minmax(0, 1fr) auto;
  gap: 12px;
  align-items: end;
}
.field {
  display: flex;
  flex-direction: column;
  gap: 5px;
  min-width: 0;
}
.field :deep(.el-select),
.field :deep(.el-input) {
  width: 100%;
}
.field-label {
  display: flex;
  align-items: center;
  gap: 6px;
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--color-text-strong);
}
.field-label::before {
  content: "";
  width: 6px;
  height: 6px;
  flex: none;
  border-radius: 50%;
  background: #000;
}
.filter-actions {
  display: flex;
  gap: 8px;
  flex: none;
}
.filter-actions :deep(.el-button) {
  height: 38px;
  font-family: var(--font-mono);
  font-size: 12px;
  font-weight: 700;
}
.apply-btn {
  background: #000;
  color: #fff;
}
.apply-btn:hover {
  background: #14171A;
  color: #fff;
}
.filter-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  padding-top: 10px;
  border-top: 1px solid var(--color-divider);
}
.stat-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.stat-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 3px 10px;
  border: 1.5px solid #000;
  border-radius: var(--radius-tag);
  background: #f7f9fb;
  font-size: 11px;
  font-weight: 600;
  color: var(--text-tertiary);
}
.stat-chip strong {
  font-size: 12px;
  color: var(--color-text-strong);
}
.foot-page {
  font-size: 11px;
  letter-spacing: 0.04em;
  color: var(--text-tertiary);
}

/* ---------- 表格面板 ---------- */
.table-panel {
  display: flex;
  flex-direction: column;
}
.panel-meta {
  font-size: 10px;
  letter-spacing: 0.08em;
  color: var(--text-tertiary);
}
.set-table {
  width: 100%;
}
.set-table :deep(.el-table__inner-wrapper::before) {
  display: none;
}
.set-table :deep(th.el-table__cell) {
  padding: 10px 12px;
}
.set-table :deep(td.el-table__cell) {
  padding: 12px;
  vertical-align: top;
}
.set-table :deep(.row-vision) {
  --el-table-row-hover-bg-color: #F7F9FB;
}
.set-table :deep(.row-chat) {
  --el-table-row-hover-bg-color: #F7F9FB;
}
.row-index {
  color: var(--text-tertiary);
  font-size: 11px;
  font-weight: 700;
}
.set-cell {
  display: flex;
  flex-direction: column;
  gap: 3px;
  min-width: 0;
}
.set-name {
  font-size: 14px;
  font-weight: 700;
  line-height: 1.35;
  color: var(--color-text-strong);
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}
.set-desc {
  font-size: 11px;
  color: var(--text-tertiary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.set-items-link {
  align-self: flex-start;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  margin-top: 2px;
  padding: 0;
  border: none;
  background: none;
  font-size: 11px;
  font-weight: 700;
  color: var(--primary);
  cursor: pointer;
}
.set-items-link:hover {
  text-decoration: underline;
}
.type-chip {
  gap: 5px;
  box-shadow: 1px 1px 0 #000;
}
.chip-vision {
  background: #EAEEFD;
  color: #2643BC;
}
.chip-chat {
  background: #EAEEFD;
  color: #7C3AED;
}
.count-strong {
  font-size: 13px;
  font-weight: 700;
  color: var(--color-text-strong);
}
.count-unit {
  margin-left: 2px;
  font-size: 11px;
  color: var(--text-tertiary);
}
.creator-cell {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
  max-width: 100%;
}
.creator-avatar {
  width: 20px;
  height: 20px;
  flex: none;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px solid #000;
  border-radius: 50%;
  background: #F7F9FB;
  color: var(--color-text-strong);
  font-size: 11px;
}
.creator-name {
  font-size: 11px;
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.cell-dim {
  font-size: 11px;
  color: var(--text-tertiary);
}
.cell-strong {
  font-size: 13px;
  font-weight: 700;
  color: var(--color-text-strong);
}
.nowrap {
  white-space: nowrap;
}
.row-actions {
  display: inline-flex;
  align-items: center;
  justify-content: flex-end;
  gap: 6px;
}
.row-actions :deep(.el-button) {
  height: 26px;
  padding: 0 8px;
  font-size: 11px;
  font-weight: 700;
  box-shadow: 2px 2px 0 #000;
}
.row-link {
  padding: 2px 4px;
  border: none;
  background: none;
  font-family: var(--font);
  font-size: 11px;
  font-weight: 700;
  color: var(--text-tertiary);
  cursor: pointer;
}
.row-link:hover:not(:disabled) {
  color: var(--color-text-strong);
  text-decoration: underline;
}
.row-link:disabled {
  cursor: not-allowed;
  opacity: 0.55;
}
.row-link--danger {
  color: var(--danger-text);
}
.row-link--danger:hover {
  color: var(--danger-text);
  text-decoration: underline;
}

/* ---------- 表格底部：分页 ---------- */
.table-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  padding: 10px 14px;
  border-top: 2px solid #000;
  background: #f7f9fb;
}
.foot-info {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  font-size: 12px;
  color: var(--text-secondary);
}
.foot-divider {
  color: #E1E8ED;
}
.size-box {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
}
.page-size {
  width: 92px;
}
.page-size :deep(.el-select__wrapper) {
  min-height: 26px;
  box-shadow: 0 0 0 1.5px #000 inset;
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 700;
}
.table-foot :deep(.el-pagination) {
  gap: 4px;
}
.table-foot :deep(.el-pagination .el-pager li),
.table-foot :deep(.el-pagination button) {
  min-width: 28px;
  height: 28px;
  padding: 0 4px;
  border: 2px solid #000;
  border-radius: var(--radius-input);
  background: #ffffff;
  box-shadow: 2px 2px 0 #000;
  font-family: var(--font-mono);
  font-size: 12px;
  font-weight: 700;
  color: var(--text-secondary);
}
.table-foot :deep(.el-pagination .el-pager li.is-active) {
  background-image: var(--gradient-brand);
  color: #ffffff;
}
.table-foot :deep(.el-pagination button:disabled) {
  background: #EAEEFD;
  color: #9aa4ae;
  box-shadow: none;
  cursor: not-allowed;
}
.table-foot :deep(.el-pagination .el-pager li:not(.is-active):hover),
.table-foot :deep(.el-pagination button:not(:disabled):hover) {
  background: #eaeefd;
  color: var(--accent);
}

/* ---------- 弹窗通用：自定义头部 ---------- */
:deep(.ts-dialog.el-dialog) {
  padding: 0;
  border: 2px solid #000;
  border-radius: var(--radius-dialog);
  box-shadow: var(--shadow-dialog);
  overflow: hidden;
  max-width: calc(100vw - 32px);
}
:deep(.ts-dialog .el-dialog__header) {
  margin: 0;
  padding: 0;
  border-bottom: 0;
}
:deep(.ts-dialog .el-dialog__body) {
  padding: 0;
}
:deep(.ts-dialog .el-dialog__footer) {
  padding: 0;
  border-top: 0;
}
.dlg-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 16px;
  border-bottom: 2px solid #000;
}
.dlg-head--brand {
  background: var(--gradient-brand);
  color: #fff;
}
.dlg-head--dark {
  background: #000;
  color: #fff;
}
.dlg-head--plain {
  background: #fff;
  color: var(--color-text-strong);
}
.dlg-head-main {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}
.dlg-head-icon {
  width: 32px;
  height: 32px;
  flex: none;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 2px solid #000;
  border-radius: var(--radius-input);
  background: #fff;
  color: #000;
  font-size: 16px;
}
.dlg-head-text {
  min-width: 0;
}
.dlg-head-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-family: var(--font-headline);
  font-size: 15px;
  font-weight: 700;
  line-height: 1.35;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.dlg-head-en {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.08em;
  opacity: 0.8;
}
.dlg-head-sub {
  margin: 1px 0 0;
  font-size: 10.5px;
  letter-spacing: 0.06em;
  opacity: 0.72;
}
.dlg-head--plain .dlg-head-sub {
  color: var(--text-tertiary);
  opacity: 1;
}
.hist-dot {
  width: 12px;
  height: 12px;
  flex: none;
  border: 1.5px solid #fff;
  border-radius: 50%;
  background: var(--success);
}
.dlg-close {
  width: 28px;
  height: 28px;
  flex: none;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 2px solid #000;
  border-radius: var(--radius-input);
  background: #fff;
  color: #000;
  cursor: pointer;
  transition: all 0.15s ease;
}
.dlg-close:hover {
  background: var(--danger-light);
  color: var(--danger-text);
  transform: translate(1px, 1px);
}
.dlg-head--dark .dlg-close {
  border-color: #fff;
}
.dlg-head--dark .dlg-close:hover {
  background: var(--danger);
  color: #fff;
}
.dlg-body {
  padding: 16px;
}
.dlg-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  padding: 12px 16px;
  background: #EAEEFD;
  border-top: 2px solid #000;
}
.foot-hint {
  font-size: 10px;
  letter-spacing: 0.06em;
  color: var(--text-tertiary);
}
.foot-btns {
  display: flex;
  gap: 10px;
}
.dark-btn {
  background: #000;
  color: #fff;
}
.dark-btn:hover {
  background: #14171A;
  color: #fff;
}
.nb-note {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 8px 10px;
  border: 1px solid #000;
  border-radius: var(--radius-input);
  background: #f7f9fb;
  font-size: 11.5px;
  line-height: 1.55;
  color: var(--text-secondary);
}
.nb-note :deep(.el-icon) {
  flex: none;
  margin-top: 2px;
  color: var(--primary);
}
.nb-note p {
  margin: 0;
}

/* ---------- 新建测试集 ---------- */
.create-body {
  padding: 16px;
}
.create-form :deep(.el-form-item) {
  margin-bottom: 12px;
}
.create-form :deep(.el-form-item__label) {
  padding-bottom: 4px;
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  line-height: 1.4;
  color: var(--color-text-strong);
}
.type-radio :deep(.el-radio) {
  margin-right: 20px;
  font-size: 12px;
  font-weight: 700;
  color: var(--color-text-strong);
}

/* ---------- 条目查看 ---------- */
.items-body {
  padding: 14px 16px;
}
.items-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
  font-size: 11px;
  color: var(--text-tertiary);
}
.items-head :deep(.el-pagination) {
  gap: 4px;
}
.items-head :deep(.el-pagination .el-pager li),
.items-head :deep(.el-pagination button) {
  min-width: 26px;
  height: 26px;
  padding: 0 4px;
  border: 2px solid #000;
  border-radius: var(--radius-input);
  background: #fff;
  box-shadow: 2px 2px 0 #000;
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 700;
}
.items-head :deep(.el-pagination .el-pager li.is-active) {
  background-image: var(--gradient-brand);
  color: #fff;
}
.items-head :deep(.el-pagination button:disabled) {
  box-shadow: none;
  background: #EAEEFD;
  color: #9aa4ae;
}
.items-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 14px;
  max-height: 64vh;
  overflow-y: auto;
}
.item-card {
  border: 2px solid #000;
  border-radius: var(--radius-card);
  overflow: hidden;
  background: #fff;
}
/* 图片自然撑开容器：标注框百分比坐标与图片像素严格对齐 */
.img-wrap {
  position: relative;
  background: #F7F9FB;
}
.img-wrap img {
  width: 100%;
  display: block;
}
.det-box {
  position: absolute;
  border: 1.5px solid #ef4444;
  box-sizing: border-box;
}
.det-label {
  position: absolute;
  left: -1.5px;
  top: -16px;
  padding: 0 3px;
  border-radius: 2px;
  background: #ef4444;
  color: #fff;
  font-size: 10px;
  line-height: 14px;
  white-space: nowrap;
}
.item-meta {
  display: flex;
  justify-content: space-between;
  padding: 6px 8px;
  font-size: 12px;
}
.item-src {
  color: var(--color-text-strong);
  font-weight: 600;
}
.item-count {
  color: var(--text-tertiary);
}

/* chat 问答列表 */
.qa-list {
  max-height: 64vh;
  overflow-y: auto;
}
.qa-card {
  padding: 12px 14px;
  border: 2px solid #000;
  border-radius: var(--radius-card);
  margin-bottom: 10px;
  background: #fff;
}
.qa-q,
.qa-a {
  display: flex;
  gap: 8px;
  align-items: flex-start;
  font-size: 14px;
  line-height: 1.6;
}
.qa-a {
  margin-top: 8px;
  color: var(--text-secondary);
}
.qa-tag {
  flex-shrink: 0;
  width: 20px;
  height: 20px;
  border-radius: var(--radius-input);
  background: var(--primary);
  color: #fff;
  font-size: 12px;
  text-align: center;
  line-height: 20px;
}
.qa-tag-a {
  background: var(--accent);
}

/* ---------- 运行评测 ---------- */
.eval-body {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.target-card {
  padding: 10px 12px;
  border: 2px solid #000;
  border-radius: var(--radius-input);
  background: #f7f9fb;
}
.target-label {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.09em;
  color: var(--text-tertiary);
}
.target-name {
  margin-top: 2px;
  font-size: 13px;
  font-weight: 700;
  color: var(--color-text-strong);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.target-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 6px;
}
.target-count {
  font-size: 11px;
  color: var(--text-tertiary);
}
.target-empty {
  margin-top: 4px;
  font-size: 11px;
  line-height: 1.55;
  color: var(--text-tertiary);
}
.eval-form :deep(.el-form-item) {
  margin-bottom: 12px;
}
.eval-form :deep(.el-form-item__label) {
  padding-bottom: 4px;
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  line-height: 1.5;
  color: var(--color-text-strong);
}
.form-label {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.label-chip {
  padding: 0 5px;
  border: 1px solid #000;
  border-radius: 2px;
  background: #EAEEFD;
  font-size: 9.5px;
  letter-spacing: 0.04em;
}

/* ---------- 测试历史 ---------- */
.history-body {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 14px 16px;
  max-height: 64vh;
  overflow-y: auto;
}
.history-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  font-size: 11px;
  color: var(--text-tertiary);
}
.history-head :deep(.el-button) {
  height: 26px;
  font-size: 11px;
  font-weight: 700;
  box-shadow: 2px 2px 0 #000;
}
.history-table {
  width: 100%;
}
.history-table :deep(.el-table__inner-wrapper::before) {
  display: none;
}
.history-table :deep(th.el-table__cell) {
  padding: 8px 10px;
}
.history-table :deep(td.el-table__cell) {
  padding: 9px 10px;
  vertical-align: middle;
}
.history-table :deep(.hist-row-running td.el-table__cell) {
  background: #F7F9FB;
}
.history-table :deep(.el-table__expand-icon) {
  color: var(--text-secondary);
}
.hist-set-name {
  font-size: 11.5px;
  font-weight: 600;
  color: var(--color-text-strong);
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}
.model-name {
  font-size: 12px;
  font-weight: 700;
  color: var(--color-text-strong);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.model-sub {
  font-size: 10px;
  color: var(--text-tertiary);
}
.metric-main {
  font-size: 12.5px;
  font-weight: 700;
  color: var(--color-text-strong);
}
.metric-main--accent {
  color: var(--primary);
}
.metric-sub {
  font-size: 10.5px;
  font-weight: 700;
  color: var(--text-secondary);
}
.metric-running {
  font-size: 11px;
  font-style: italic;
  color: var(--text-tertiary);
}
.status-chip {
  gap: 5px;
}
.chip-dot {
  width: 5px;
  height: 5px;
  flex: none;
  border-radius: 50%;
  background: currentColor;
}
.chip-spin {
  width: 8px;
  height: 8px;
  flex: none;
  border: 1.5px solid currentColor;
  border-top-color: transparent;
  border-radius: 50%;
  animation: ts-spin 0.9s linear infinite;
}
@keyframes ts-spin {
  to {
    transform: rotate(360deg);
  }
}
.hist-foot-note {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  padding: 9px 12px;
  border: 2px solid #000;
  border-radius: var(--radius-input);
  background: #f7f9fb;
}
.hist-note-text {
  font-size: 11px;
  line-height: 1.5;
  color: var(--text-tertiary);
}
.ghost-btn {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  flex: none;
  padding: 4px 9px;
  border: 1.5px solid #000;
  border-radius: var(--radius-input);
  background: #fff;
  color: var(--color-text-strong);
  font-size: 11px;
  font-weight: 700;
  cursor: pointer;
}
.ghost-btn:disabled {
  cursor: not-allowed;
  opacity: 0.5;
}
.history-detail {
  padding: 4px 12px;
}
.mt8 {
  margin-top: 8px;
}
.history-error {
  margin-top: 10px;
  padding: 8px 12px;
  border: 1.5px solid var(--danger);
  border-radius: var(--radius-input);
  color: var(--danger-text);
  font-size: 13px;
}
.history-items {
  margin-top: 10px;
}
.history-items-title {
  font-size: 13px;
  font-weight: 600;
  margin-bottom: 6px;
}
.history-item-line {
  display: flex;
  gap: 16px;
  align-items: center;
  padding: 4px 0;
  border-top: 1px dashed var(--color-divider);
  font-size: 12px;
  color: var(--text-tertiary);
}
.history-item-line .ellipsis {
  flex: 1;
  min-width: 0;
  color: var(--color-text-strong);
}
.err-text {
  color: var(--danger-text);
}

/* ---------- 窄屏 ---------- */
@media (max-width: 1000px) {
  .filter-grid {
    grid-template-columns: 1fr;
    align-items: stretch;
  }
  .testset-head {
    flex-direction: column;
    align-items: flex-start;
  }
  .items-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}
</style>
