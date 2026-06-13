<script setup>
import { onMounted, reactive, ref } from 'vue'
import { CheckCircle2, Clock, RefreshCcw, Save, Users } from 'lucide-vue-next'

import { appointmentApi } from '../api/modules'
import DataTable from '../components/DataTable.vue'
import EmptyState from '../components/EmptyState.vue'
import MessageBar from '../components/MessageBar.vue'
import StatusBadge from '../components/StatusBadge.vue'
import { appointmentStatuses, subjects, timeSlots, waitlistStatuses } from '../constants/options'

const appointments = ref([])
const waitlist = ref([])
const loading = ref(false)
const waitlistLoading = ref(false)
const saving = ref(false)
const waitlistSaving = ref(false)
const message = reactive({ text: '', type: 'info' })
const notifyMessage = reactive({ text: '', type: 'info', visible: false })

const form = reactive({
  studentName: '',
  idNumber: '',
  subject: '科目一',
  examDate: '',
  timeslot: timeSlots[0]
})

const waitlistForm = reactive({
  studentName: '',
  idNumber: '',
  subject: '科目一',
  examDate: '',
  timeslot: timeSlots[0]
})

const appointmentColumns = [
  { key: 'studentName', label: '学员' },
  { key: 'idNumber', label: '证件号' },
  { key: 'subject', label: '科目' },
  { key: 'examDate', label: '日期' },
  { key: 'timeslot', label: '时段' },
  { key: 'status', label: '状态' }
]

const waitlistColumns = [
  { key: 'position', label: '排位' },
  { key: 'studentName', label: '学员' },
  { key: 'idNumber', label: '证件号' },
  { key: 'subject', label: '科目' },
  { key: 'examDate', label: '日期' },
  { key: 'timeslot', label: '时段' },
  { key: 'status', label: '状态' }
]

function setMessage(text, type = 'info') {
  message.text = text
  message.type = type
}

function showNotify(text, type = 'info') {
  notifyMessage.text = text
  notifyMessage.type = type
  notifyMessage.visible = true
  setTimeout(() => {
    notifyMessage.visible = false
  }, 5000)
}

async function loadAppointments() {
  loading.value = true
  try {
    appointments.value = await appointmentApi.list()
  } catch (error) {
    setMessage(error.message, 'error')
  } finally {
    loading.value = false
  }
}

async function loadWaitlist() {
  waitlistLoading.value = true
  try {
    waitlist.value = await appointmentApi.waitlistList()
  } catch (error) {
    console.error(error)
  } finally {
    waitlistLoading.value = false
  }
}

async function loadAll() {
  await Promise.all([loadAppointments(), loadWaitlist()])
}

async function submitAppointment() {
  saving.value = true
  setMessage('')
  try {
    await appointmentApi.create({ ...form })
    Object.assign(form, {
      studentName: '',
      idNumber: '',
      subject: form.subject,
      examDate: '',
      timeslot: form.timeslot
    })
    setMessage('预约已提交', 'success')
    await loadAppointments()
  } catch (error) {
    setMessage(error.message, 'error')
  } finally {
    saving.value = false
  }
}

async function submitWaitlist() {
  waitlistSaving.value = true
  setMessage('')
  try {
    await appointmentApi.waitlistCreate({ ...waitlistForm })
    Object.assign(waitlistForm, {
      studentName: '',
      idNumber: '',
      subject: waitlistForm.subject,
      examDate: '',
      timeslot: waitlistForm.timeslot
    })
    setMessage('已加入候补队列', 'success')
    await loadWaitlist()
  } catch (error) {
    setMessage(error.message, 'error')
  } finally {
    waitlistSaving.value = false
  }
}

async function changeStatus(row, status) {
  try {
    const result = await appointmentApi.updateStatus(row.id, status)
    if (result.filledFromWaitlist) {
      showNotify(
        `候补学员 ${result.filledFromWaitlist.studentName} 已自动补位成功`,
        'success'
      )
    }
    await loadAll()
  } catch (error) {
    setMessage(error.message, 'error')
  }
}

async function changeWaitlistStatus(row, status) {
  try {
    await appointmentApi.waitlistUpdateStatus(row.id, status)
    await loadWaitlist()
  } catch (error) {
    setMessage(error.message, 'error')
  }
}

onMounted(loadAll)
</script>

<template>
  <div class="appointment-page">
    <div v-if="notifyMessage.visible" class="notify-bar" :class="notifyMessage.type">
      <CheckCircle2 :size="18" />
      <span>{{ notifyMessage.text }}</span>
    </div>

    <section class="module-grid two-columns">
      <form class="panel form-panel" @submit.prevent="submitAppointment">
        <div class="panel-heading">
          <div>
            <h3>新建预约</h3>
            <p>按约考规则校验日期、科目名额和重复预约。</p>
          </div>
          <Save :size="20" />
        </div>

        <MessageBar :message="message.text" :type="message.type" />

        <label>
          <span>学员姓名</span>
          <input v-model.trim="form.studentName" required placeholder="请输入姓名" />
        </label>
        <label>
          <span>证件号</span>
          <input v-model.trim="form.idNumber" required placeholder="身份证或档案号" />
        </label>
        <div class="field-row">
          <label>
            <span>预约科目</span>
            <select v-model="form.subject">
              <option v-for="subject in subjects" :key="subject">{{ subject }}</option>
            </select>
          </label>
          <label>
            <span>考试日期</span>
            <input v-model="form.examDate" required type="date" />
          </label>
        </div>
        <label>
          <span>考试时段</span>
          <select v-model="form.timeslot">
            <option v-for="slot in timeSlots" :key="slot">{{ slot }}</option>
          </select>
        </label>

        <button class="primary-button" :disabled="saving" type="submit">
          <CheckCircle2 :size="18" />
          <span>{{ saving ? '提交中' : '提交预约' }}</span>
        </button>
      </form>

      <form class="panel form-panel" @submit.prevent="submitWaitlist">
        <div class="panel-heading">
          <div>
            <h3>候补排队</h3>
            <p>名额满时加入候补，取消后自动按序补位。</p>
          </div>
          <Users :size="20" />
        </div>

        <label>
          <span>学员姓名</span>
          <input v-model.trim="waitlistForm.studentName" required placeholder="请输入姓名" />
        </label>
        <label>
          <span>证件号</span>
          <input v-model.trim="waitlistForm.idNumber" required placeholder="身份证或档案号" />
        </label>
        <div class="field-row">
          <label>
            <span>预约科目</span>
            <select v-model="waitlistForm.subject">
              <option v-for="subject in subjects" :key="subject">{{ subject }}</option>
            </select>
          </label>
          <label>
            <span>考试日期</span>
            <input v-model="waitlistForm.examDate" required type="date" />
          </label>
        </div>
        <label>
          <span>考试时段</span>
          <select v-model="waitlistForm.timeslot">
            <option v-for="slot in timeSlots" :key="slot">{{ slot }}</option>
          </select>
        </label>

        <button class="secondary-button" :disabled="waitlistSaving" type="submit">
          <Clock :size="18" />
          <span>{{ waitlistSaving ? '提交中' : '加入候补' }}</span>
        </button>
      </form>
    </section>

    <section class="panel list-panel">
      <div class="panel-heading">
        <div>
          <h3>预约列表</h3>
          <p>维护当前预约状态。</p>
        </div>
        <button class="icon-button" type="button" title="刷新" @click="loadAppointments">
          <RefreshCcw :size="18" />
        </button>
      </div>

      <EmptyState
        v-if="!loading && appointments.length === 0"
        title="暂无预约"
        description="提交预约后将在这里显示。"
      />
      <DataTable v-else :columns="appointmentColumns" :rows="appointments">
        <template #status="{ row }">
          <StatusBadge :status="row.status" />
        </template>
        <template #actions="{ row }">
          <select class="compact-select" :value="row.status" @change="changeStatus(row, $event.target.value)">
            <option v-for="status in appointmentStatuses" :key="status">{{ status }}</option>
          </select>
        </template>
      </DataTable>
    </section>

    <section class="panel list-panel">
      <div class="panel-heading">
        <div>
          <h3>候补队列</h3>
          <p>按加入顺序排列，有名额时自动补位。</p>
        </div>
        <button class="icon-button" type="button" title="刷新" @click="loadWaitlist">
          <RefreshCcw :size="18" />
        </button>
      </div>

      <EmptyState
        v-if="!waitlistLoading && waitlist.length === 0"
        title="暂无候补"
        description="加入候补后将在这里显示。"
      />
      <DataTable v-else :columns="waitlistColumns" :rows="waitlist">
        <template #position="{ row }">
          <span class="position-badge">#{{ row.position }}</span>
        </template>
        <template #status="{ row }">
          <StatusBadge :status="row.status" />
        </template>
        <template #actions="{ row }">
          <select
            v-if="row.status === '候补中'"
            class="compact-select"
            :value="row.status"
            @change="changeWaitlistStatus(row, $event.target.value)"
          >
            <option v-for="status in waitlistStatuses" :key="status">{{ status }}</option>
          </select>
          <span v-else class="muted-text">{{ row.status }}</span>
        </template>
      </DataTable>
    </section>
  </div>
</template>

<style scoped>
.appointment-page {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.notify-bar {
  position: sticky;
  top: 0;
  z-index: 100;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  border-radius: 8px;
  font-weight: 500;
  animation: slideDown 0.3s ease-out;
}

.notify-bar.success {
  background: #dcfce7;
  color: #166534;
  border: 1px solid #bbf7d0;
}

.notify-bar.error {
  background: #fee2e2;
  color: #991b1b;
  border: 1px solid #fecaca;
}

.notify-bar.info {
  background: #dbeafe;
  color: #1e40af;
  border: 1px solid #bfdbfe;
}

@keyframes slideDown {
  from {
    opacity: 0;
    transform: translateY(-10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.position-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 36px;
  height: 24px;
  padding: 0 8px;
  background: #e0e7ff;
  color: #3730a3;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 600;
}

.muted-text {
  color: #9ca3af;
  font-size: 13px;
}

.secondary-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  width: 100%;
  height: 42px;
  border: none;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
  background: #f3f4f6;
  color: #374151;
}

.secondary-button:hover:not(:disabled) {
  background: #e5e7eb;
}

.secondary-button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
</style>
