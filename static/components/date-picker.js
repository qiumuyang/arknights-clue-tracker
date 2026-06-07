document.addEventListener('alpine:init', () => {
  Alpine.data('datePicker', (cfg) => ({
    open: false,
    value: '',
    offset: cfg.initDays != null ? cfg.initDays : 7,
    init() {
      const tpl = document.getElementById('date-picker-tpl');
      if (tpl) {
        this.$el.appendChild(tpl.content.cloneNode(true));
        const child = this.$el.firstElementChild;
        if (child) Alpine.initTree(child);
      }
      if (this.offset > 0) this.select(this.offset);
    },
    get label() {
      if (this.offset === 0) return '今天';
      if (this.offset === -2) return '不限';
      if (!this.value) return '选择日期';
      return this.value;
    },
    select(days) {
      this.offset = days;
      this.open = false;
      if (days === 0) {
        this.value = new Date().toISOString().slice(0, 10);
      } else {
        this.value = new Date(Date.now() - days * 86400000).toISOString().slice(0, 10);
      }
      this.$dispatch('date-change', this.value);
    },
    clear() {
      this.offset = -2;
      this.value = '';
      this.open = false;
      this.$dispatch('date-change', '');
    },
    onCustom() {
      this.offset = -1;
      this.open = false;
      this.$dispatch('date-change', this.value);
    }
  }));
});
