type CheckboxItemProps = {
  label: string;
  checked: boolean;
  onChange: () => void;
};

function CheckboxItem({ label, checked, onChange }: CheckboxItemProps) {
  return (
    <label className="checkbox-item">
      <input type="checkbox" checked={checked} onChange={onChange} />
      <span>{label}</span>
    </label>
  );
}

export default CheckboxItem;