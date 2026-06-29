import { useEffect, useMemo, useState } from "react";
import { createTask, deleteTask, getTasks, runTask, updateTask } from "../../api";
import type { ProductTask } from "../../types";
import { StatusBadge } from "../../shared/components/StatusBadge";

function taskTone(task: ProductTask): "ok" | "warning" | "neutral" {
  if (task.status === "active") {
    return "ok";
  }
  if (task.status === "paused") {
    return "warning";
  }
  return "neutral";
}

function taskStatus(task: ProductTask) {
  if (task.status === "active") {
    return "启用";
  }
  if (task.status === "paused") {
    return "暂停";
  }
  if (task.status === "completed") {
    return "已完成";
  }
  return task.status || "未同步";
}

function scheduleLabel(task: ProductTask) {
  if (task.schedule === "daily") {
    return "每天";
  }
  return "一次";
}

function taskKindLabel(kind: string) {
  if (kind === "daily_summary") {
    return "定时总结";
  }
  if (kind === "check") {
    return "定时检查";
  }
  return "提醒";
}

function displayTime(value: string) {
  if (!value) {
    return "未设置时间";
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return parsed.toLocaleString();
}

export function TasksPage() {
  const [tasks, setTasks] = useState<ProductTask[]>([]);
  const [title, setTitle] = useState("");
  const [dueAt, setDueAt] = useState("");
  const [prompt, setPrompt] = useState("");
  const [kind, setKind] = useState("reminder");
  const [schedule, setSchedule] = useState("once");
  const [busyId, setBusyId] = useState("");
  const [message, setMessage] = useState("");

  const counts = useMemo(
    () => ({
      active: tasks.filter((task) => task.status === "active").length,
      paused: tasks.filter((task) => task.status === "paused").length,
      completed: tasks.filter((task) => task.status === "completed").length
    }),
    [tasks]
  );

  async function load() {
    setMessage("");
    try {
      setTasks(await getTasks());
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "任务读取失败。");
    }
  }

  useEffect(() => {
    void load();
  }, []);

  async function addTask() {
    if (!title.trim() || !prompt.trim() || !dueAt.trim()) {
      setMessage("任务标题、内容和运行时间都要填写。");
      return;
    }
    setBusyId("new");
    setMessage("");
    try {
      const task = await createTask(title, prompt, dueAt, kind, schedule);
      setTasks((current) => [task, ...current]);
      setTitle("");
      setDueAt("");
      setPrompt("");
      setKind("reminder");
      setSchedule("once");
      setMessage("任务已保存。");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "任务保存失败。");
    } finally {
      setBusyId("");
    }
  }

  async function toggleTask(task: ProductTask) {
    setBusyId(task.id);
    try {
      const updated = await updateTask(task.id, { enabled: task.status !== "active", completed: false });
      setTasks((current) => current.map((item) => (item.id === updated.id ? updated : item)));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "任务状态保存失败。");
    } finally {
      setBusyId("");
    }
  }

  async function completeTask(task: ProductTask) {
    setBusyId(task.id);
    try {
      const updated = await updateTask(task.id, { completed: task.status !== "completed" });
      setTasks((current) => current.map((item) => (item.id === updated.id ? updated : item)));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "任务完成状态保存失败。");
    } finally {
      setBusyId("");
    }
  }

  async function runTaskNow(task: ProductTask) {
    setBusyId(task.id);
    try {
      const result = await runTask(task.id);
      setTasks((current) => current.map((item) => (item.id === result.task.id ? result.task : item)));
      setMessage(result.run.message);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "任务运行记录失败。");
    } finally {
      setBusyId("");
    }
  }

  async function removeTask(task: ProductTask) {
    if (!window.confirm("确定删除这个任务吗？")) {
      return;
    }
    setBusyId(task.id);
    try {
      await deleteTask(task.id);
      setTasks((current) => current.filter((item) => item.id !== task.id));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "任务删除失败。");
    } finally {
      setBusyId("");
    }
  }

  return (
    <section className="productPage taskPage">
      <header className="productPageHeader">
        <div>
          <h2>任务</h2>
          <p>提醒、定时总结和定时检查会由本地服务按本机时间执行；微信主动投递仍需要安全确认。</p>
        </div>
        <div className="metricPills">
          <StatusBadge tone="ok">启用 {counts.active}</StatusBadge>
          <StatusBadge tone="warning">暂停 {counts.paused}</StatusBadge>
          <StatusBadge>完成 {counts.completed}</StatusBadge>
        </div>
      </header>

      <article className="productPanel">
        <h3>新建任务</h3>
        <div className="controlFormGrid">
          <input value={title} onChange={(event) => setTitle(event.target.value)} placeholder="标题" />
          <input type="datetime-local" value={dueAt} onChange={(event) => setDueAt(event.target.value)} aria-label="运行时间" />
          <select value={kind} onChange={(event) => setKind(event.target.value)} aria-label="任务类型">
            <option value="reminder">提醒</option>
            <option value="daily_summary">定时总结</option>
            <option value="check">定时检查</option>
          </select>
          <select value={schedule} onChange={(event) => setSchedule(event.target.value)} aria-label="计划">
            <option value="once">一次</option>
            <option value="daily">每天</option>
          </select>
          <textarea value={prompt} onChange={(event) => setPrompt(event.target.value)} placeholder="任务内容" />
          <button type="button" onClick={() => void addTask()} disabled={busyId === "new"}>
            保存任务
          </button>
        </div>
      </article>

      <div className="productList taskList">
        {tasks.map((task) => (
          <article key={task.id} className="productPanel taskCard">
            <header>
              <div>
                <strong>{task.title}</strong>
                <span>
                  {displayTime(task.next_run_at || task.due_at)} · {taskKindLabel(task.kind)} · {scheduleLabel(task)}
                </span>
              </div>
              <StatusBadge tone={taskTone(task)}>{taskStatus(task)}</StatusBadge>
            </header>
            <p>{task.prompt}</p>
            {task.last_result && <p>{task.last_result}</p>}
            {task.last_error && <p className="dangerText">{task.last_error}</p>}
            {task.run_history.length > 0 && (
              <div className="taskRunHistory">
                {task.run_history.slice(-3).map((run) => (
                  <span key={`${task.id}-${run.ran_at}-${run.trigger || "run"}`}>
                    {displayTime(run.ran_at)} · {run.trigger === "scheduled" ? "自动" : "手动"} · {run.message}
                  </span>
                ))}
              </div>
            )}
            <div className="actionRow">
              <button type="button" className="secondaryButton compactButton" onClick={() => void runTaskNow(task)} disabled={busyId === task.id}>
                立即运行
              </button>
              <button type="button" className="secondaryButton compactButton" onClick={() => void toggleTask(task)} disabled={busyId === task.id}>
                {task.status === "active" ? "暂停" : "启用"}
              </button>
              <button type="button" className="secondaryButton compactButton" onClick={() => void completeTask(task)} disabled={busyId === task.id}>
                {task.status === "completed" ? "恢复" : "完成"}
              </button>
              <button type="button" className="secondaryButton compactButton dangerMiniButton" onClick={() => void removeTask(task)} disabled={busyId === task.id}>
                删除
              </button>
            </div>
          </article>
        ))}
        {tasks.length === 0 && (
          <article className="productPanel">
            <p>还没有任务。</p>
          </article>
        )}
      </div>
      {message && <p className="inlineStatus">{message}</p>}
    </section>
  );
}
