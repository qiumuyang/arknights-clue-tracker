document.addEventListener('alpine:init', () => {
  Alpine.data('app', () => ({
    tab: 'record',

    async api(path, opts = {}) {
      const r = await fetch(path, opts);
      if (!r.ok) { const e = await r.json().catch(() => ({})); throw new Error(e.detail || r.statusText); }
      return r.json();
    },

    showToast(msg, ok = true) {
      const el = document.createElement('div');
      el.className = 'toast ' + (ok ? 'success' : 'error');
      el.textContent = msg;
      document.body.appendChild(el);
      setTimeout(() => el.remove(), 2600);
    },

    fmtTime(iso) {
      const d = new Date(iso);
      const pad = n => String(n).padStart(2, '0');
      return `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
    },

    fmtNum(n) {
      return n > 0 ? '+' + n : String(n);
    },

    switchTab(t) {
      this.tab = t;
      if (t === 'advice') this.loadAdvice();
      if (t === 'history') this.loadHistory();
      if (t === 'record') this.loadSummary();
    },

    // ====== Confirm Modal ======
    confirmModal: {
      show: false,
      title: '',
      message: '',
      confirmText: '确认',
      onConfirm: () => {},
    },

    showConfirm(title, message, confirmText, onConfirm, confirmClass = 'btn-danger') {
      this.confirmModal.show = true;
      this.confirmModal.title = title;
      this.confirmModal.message = message;
      this.confirmModal.confirmText = confirmText;
      this.confirmModal.onConfirm = onConfirm;
      this.confirmModal.confirmClass = confirmClass;
    },

    async toggleWasNew(r) {
      const next = !r.was_new;
      this.showConfirm(
        '切换补缺状态',
        '将 ' + r.name + ' 的线索 ' + r.clue + ' (' + r.type + ') 标记为' + (next ? '补' : '非补') + '？',
        next ? '标记补' : '取消标记',
        async () => {
          try {
            await this.api(`/api/records/${r.id}`, {
              method: 'PATCH',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ was_new: next }),
            });
            r.was_new = next;
            this.showToast(next ? '已标记为补' : '已取消补标记');
          } catch (err) {
            this.showToast(err.message, false);
          }
        },
        'btn-primary'
      );
    },
    async confirmDelRecord(r) {
      this.showConfirm('删除记录', '确定要删除 ' + r.name + ' 的线索 ' + r.clue + ' 记录吗？', '删除', async () => {
        r._deleting = true;
        try {
          await this.api(`/api/records/${r.id}`, { method: 'DELETE' });
          this.showToast('已删除');
          if (this.historyData.length === 1 && this.historyPage > 1) {
            this.historyPage--;
          }
          await this.loadHistory();
        } catch (err) {
          r._deleting = false;
          this.showToast(err.message, false);
        }
      });
    },

    // ====== Autocomplete ======
    form: { name: '', clues: [], wasNew: false, time: '' },
    acOpen: false,
    acNames: [],
    acLoading: false,
    topPlayers: [],
    async autocomplete() {
      const q = this.form.name.trim();
      if (!q) {
        this.acNames = this.topPlayers;
        this.acOpen = this.acNames.length > 0;
        return;
      }
      this.acLoading = true;
      this.acOpen = true;
      try {
        this.acNames = await this.api('/api/players?q=' + encodeURIComponent(q));
      } catch { this.acNames = []; }
      this.acLoading = false;
    },
    pickPlayer(item) {
      this.form.name = typeof item === 'string' ? item : item.name;
      this.acOpen = false;
    },
    pickHistoryPlayer(item) {
      this.historySearch = typeof item === 'string' ? item : item.name;
      this.historyAcOpen = false;
      this.historyPage = 1;
      this.loadHistory();
    },

    toggleClue(n) {
      const idx = this.form.clues.indexOf(n);
      if (idx >= 0) this.form.clues.splice(idx, 1);
      else this.form.clues.push(n);
    },

    async submitRecord(type) {
      const { name, clues, wasNew, time } = this.form;
      if (!name.trim()) { this.showToast('请输入玩家名', false); return; }
      if (!clues.length) { this.showToast('请至少选择一个线索', false); return; }
      const valid = time && !isNaN(Date.parse(time));
      let ok = 0;
      for (const clue of clues) {
        const body = { name, clue, type, was_new: wasNew };
        if (valid) body.time = time;
        try {
          await this.api('/api/records', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
          ok++;
        } catch (err) { this.showToast(err.message, false); }
      }
      if (ok) {
        this.showToast('已添加 ' + ok + ' 条');
        this.form.name = '';
        this.form.wasNew = false;
        this.form.time = '';
        this.form.clues = [];
        await this.loadSummary();
        this.flashTable();
      }
    },

    flashTable() {
      const rows = document.querySelectorAll('#summary-table tbody tr');
      if (rows.length) {
        rows[0].classList.add('flash');
        setTimeout(() => rows[0].classList.remove('flash'), 900);
      }
    },

    // ====== Import ======
    importFile: null,
    triggerImport() {
      document.getElementById('import-file').click();
    },
    onFileSelected(el) {
      if (el.files.length) this.importFile = el.files[0];
    },
    cancelImport() {
      this.importFile = null;
    },
    async confirmImport() {
      const file = this.importFile;
      if (!file) return;
      try {
        const content = await file.text();
        const res = await this.api('/api/import', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ content }) });
        this.showToast('导入: ' + res.imported + ' 条' + (res.skipped ? ' (' + res.skipped + ' 条重复已跳过)' : ''));
        this.importFile = null;
        await this.loadSummary();
      } catch (err) { this.showToast(err.message, false); }
    },

    // ====== Summary ======
    summaryData: [],
    summaryLoading: false,
    summarySince: '',
    summarySortCol: 'total',
    summarySortDir: -1,
    get sortedSummary() {
      const data = [...this.summaryData];
      const key = this.summarySortCol;
      const dir = this.summarySortDir;
      data.sort((a, b) => {
        if (key === 'name') return dir * a.name.localeCompare(b.name, 'zh');
        return dir * ((Number(a[key]) || 0) - (Number(b[key]) || 0));
      });
      return data;
    },
    sortArrowUp(col, sortCol, sortDir) {
      return sortCol === col && (sortDir === 1 || sortDir === 'asc') ? 1 : 0.2;
    },
    sortArrowDown(col, sortCol, sortDir) {
      return sortCol === col && (sortDir === -1 || sortDir === 'desc') ? 1 : 0.2;
    },
    setSort(col) {
      if (this.summarySortCol === col) this.summarySortDir = -this.summarySortDir;
      else { this.summarySortCol = col; this.summarySortDir = -1; }
    },
    async loadSummary() {
      this.summaryLoading = true;
      const params = new URLSearchParams();
      if (this.summarySince) params.set('since', this.summarySince);
      this.summaryData = await this.api('/api/summary?' + params);
      this.summaryLoading = false;
    },

    // ====== Advice ======
    adviceClue: '',
    adviceSince: '',
    adviceWeight: 0.7,
    adviceScores: [],
    adviceLoading: false,

    async loadAdvice() {
      this.adviceLoading = true;
      const params = new URLSearchParams();
      if (this.adviceSince) params.set('since', this.adviceSince);
      if (this.adviceClue) params.set('clue', this.adviceClue);
      if (this.adviceClue && this.adviceWeight < 1) params.set('weight', this.adviceWeight);
      const data = await this.api('/api/advice?' + params);
      this.adviceScores = data.scores || [];
      this.adviceLoading = false;
    },

    // ====== Theme ======
    theme: localStorage.getItem('theme') || 'auto',
    setTheme() {
      localStorage.setItem('theme', this.theme);
      this.applyTheme();
    },
    applyTheme() {
      const t = this.theme === 'auto'
        ? (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light')
        : this.theme;
      document.documentElement.setAttribute('data-theme', t);
    },

    async loadTopPlayers() {
      try {
        const data = await this.api('/api/advice?since=' + new Date(Date.now() - 14 * 86400000).toISOString().slice(0, 10));
        this.topPlayers = (data.scores || []).slice(0, 10);
      } catch { this.topPlayers = []; }
    },
    init() {
      this.applyTheme();
      window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
        if (this.theme === 'auto') this.applyTheme();
      });
      this.loadSummary();
      this.loadTopPlayers();
    },

    // ====== History Autocomplete ======
    historyAcOpen: false,
    historyAcNames: [],
    historyAcLoading: false,
    async historyAutocomplete() {
      const q = this.historySearch.trim();
      if (!q) {
        this.historyAcNames = this.topPlayers;
        this.historyAcOpen = this.historyAcNames.length > 0;
        return;
      }
      this.historyAcLoading = true;
      this.historyAcOpen = true;
      try {
        this.historyAcNames = await this.api('/api/players?q=' + encodeURIComponent(q));
      } catch { this.historyAcNames = []; }
      this.historyAcLoading = false;
    },

    // ====== History ======
    historySearch: '',
    historySince: '',
    historyClues: [],
    historyData: [],
    historyLoading: false,
    historySortCol: 'time',
    historySortDir: 'desc',
    historyPage: 1,
    historyPageSize: 20,
    historyTotal: 0,
    get historyTotalPages() {
      return Math.max(1, Math.ceil(this.historyTotal / this.historyPageSize));
    },
    setHistorySort(col) {
      if (this.historySortCol === col) {
        this.historySortDir = this.historySortDir === 'desc' ? 'asc' : 'desc';
      } else {
        this.historySortCol = col;
        this.historySortDir = 'desc';
      }
      this.historyPage = 1;
      this.loadHistory();
    },
    toggleHistoryClue(n) {
      const idx = this.historyClues.indexOf(n);
      if (idx >= 0) this.historyClues.splice(idx, 1);
      else this.historyClues.push(n);
      this.historyPage = 1;
      this.loadHistory();
    },
    historyPrevPage() {
      if (this.historyPage > 1) { this.historyPage--; this.loadHistory(); }
    },
    historyNextPage() {
      if (this.historyPage < this.historyTotalPages) { this.historyPage++; this.loadHistory(); }
    },
    async loadHistory() {
      this.historyLoading = true;
      const params = new URLSearchParams({
        page: this.historyPage,
        page_size: this.historyPageSize,
        sort_col: this.historySortCol,
        sort_dir: this.historySortDir,
      });
      if (this.historySearch.trim()) params.set('name', this.historySearch.trim());
      if (this.historySince) params.set('since', this.historySince);
      if (this.historyClues.length) {
        this.historyClues.forEach(c => params.append('clues', c));
      }
      const data = await this.api('/api/records?' + params);
      this.historyData = data.items || [];
      this.historyTotal = data.total || 0;
      this.historyLoading = false;
    },
  }));
});
