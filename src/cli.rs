//! The `exporgo` command-line interface. All interactivity (flags, prompts,
//! printing) lives here so the library stays UI-free.
use std::{io::IsTerminal, path::PathBuf, process::ExitCode};

use clap::{Parser, Subcommand, ValueEnum};

use crate::{
    check::check,
    config::{self, MachineConfig, MachineDirs},
    plan::{ChangeKind, PlannedChange},
    stamp::{NewOptions, stamp},
    tokens::{Token, TokenValues},
    update::{UpdateOptions, update},
};

#[derive(Parser)]
#[command(version, about = "Stamp and maintain science-project workspaces")]
struct Cli
{
    #[command(subcommand)]
    command: Command,
}

#[derive(Subcommand)]
enum Command
{
    /// Create a new project from the embedded template
    New
    {
        /// Human project name; the folder name is its slug
        name: String,
        /// Parent directory to create the project in
        #[arg(long, default_value = ".")]
        path: PathBuf,
        /// Project status
        #[arg(long, value_enum)]
        status: Option<Status>,
        /// Project owner (default: the machine config's `owner`)
        #[arg(long)]
        owner: Option<String>,
        /// Owner email (default: the machine config's `email`)
        #[arg(long)]
        email: Option<String>,
        /// Never prompt; unset values stay as {{TOKENS}} in context.md
        #[arg(long)]
        no_input: bool,
        /// Stamp into a non-empty directory, overwriting colliding files
        #[arg(long)]
        force: bool,
    },
    /// Report a project's drift from this binary's template
    Check
    {
        /// Project root (default: current directory)
        path: Option<PathBuf>,
    },
    /// Refresh a project's exporgo-owned files from this binary's template
    Update
    {
        /// Project root (default: current directory)
        path: Option<PathBuf>,
        /// Show what would change without writing anything
        #[arg(long)]
        dry_run: bool,
        /// Only refresh .claude/skills/exporgo/ (leaves the manifest version
        /// alone)
        #[arg(long)]
        skills_only: bool,
    },
    /// Sync this project directory with its shared remote copy (via the
    /// per-machine cache); default is pull-then-push, newest file wins
    Sync
    {
        /// One-way run; omit for the bidirectional default
        #[arg(value_enum)]
        mode: Option<SyncModeArg>,
        /// Project root (default: current directory)
        #[arg(long, default_value = ".")]
        project: PathBuf,
        /// Extra name patterns to exclude (repeatable; * wildcards; matches
        /// files and directories)
        #[arg(long)]
        exclude: Vec<String>,
        /// Also DELETE target entries absent from the source (destructive;
        /// requires an explicit push or pull)
        #[arg(long)]
        mirror: bool,
        /// Log what would happen; copy and delete nothing
        #[arg(long)]
        dry_run: bool,
    },
    /// Copy a project from the sync remote onto this machine (the way to get
    /// an existing project onto a second computer)
    Clone
    {
        /// The project name (or its slug) as it exists on the remote
        name: String,
        /// Parent directory to clone into (the project lands at
        /// <path>/<slug>)
        #[arg(long, default_value = ".")]
        path: PathBuf,
    },
    /// Show or set this machine's exporgo configuration (sync remote, default
    /// owner/email)
    Config
    {
        /// Default project owner for `exporgo new`
        #[arg(long)]
        owner: Option<String>,
        /// Default owner email for `exporgo new`
        #[arg(long)]
        email: Option<String>,
        /// This machine's path to the shared sync location (Drive mount, UNC
        /// share, ...)
        #[arg(long)]
        remote_root: Option<String>,
    },
    /// Manage documented experiments inside a project
    Experiment
    {
        #[command(subcommand)]
        command: ExperimentCommand,
    },
}

#[derive(Subcommand)]
enum ExperimentCommand
{
    /// Stamp experiments/_TEMPLATE/ into experiments/<slug>/ and fill its
    /// tokens
    New
    {
        /// Human experiment name; the folder name is its slug
        name: String,
        /// Project root (default: current directory)
        #[arg(long, default_value = ".")]
        path: PathBuf,
        /// Where this experiment's raw data may live (a hint, not a mandate)
        #[arg(long)]
        data_root: Option<String>,
        /// Processed data root
        #[arg(long)]
        processed_root: Option<String>,
        /// Never prompt; unset values stay as {{TOKENS}} in the stamped files
        #[arg(long)]
        no_input: bool,
    },
}

#[derive(Clone, Copy, ValueEnum)]
enum SyncModeArg
{
    /// Local -> cache -> remote
    Push,
    /// Remote -> cache -> local
    Pull,
}

#[derive(Clone, Copy, ValueEnum)]
enum Status
{
    Planning,
    Active,
    Analysis,
    Writing,
    Archived,
}

impl Status
{
    const ALL: [Status; 5] = [
        Status::Planning,
        Status::Active,
        Status::Analysis,
        Status::Writing,
        Status::Archived,
    ];

    fn as_str(self) -> &'static str
    {
        match self
        {
            Status::Planning => "planning",
            Status::Active => "active",
            Status::Analysis => "analysis",
            Status::Writing => "writing",
            Status::Archived => "archived",
        }
    }
}

/// Parses arguments, runs the command, prints the outcome, returns the exit
/// code.
pub fn run() -> ExitCode
{
    let cli = Cli::parse();
    let result = match cli.command
    {
        Command::New {
            name,
            path,
            status,
            owner,
            email,
            no_input,
            force,
        } => run_new(NewArgs {
            name,
            path,
            status,
            owner,
            email,
            no_input,
            force,
        }),
        Command::Check { path } => run_check(path.unwrap_or_else(|| PathBuf::from("."))),
        Command::Update {
            path,
            dry_run,
            skills_only,
        } => run_update(
            path.unwrap_or_else(|| PathBuf::from(".")),
            UpdateOptions {
                dry_run,
                skills_only,
            },
        ),
        Command::Sync {
            mode,
            project,
            exclude,
            mirror,
            dry_run,
        } => run_sync(SyncArgs {
            mode,
            project,
            exclude,
            mirror,
            dry_run,
        }),
        Command::Clone { name, path } => run_clone(name, path),
        Command::Config {
            owner,
            email,
            remote_root,
        } => run_config(owner, email, remote_root),
        Command::Experiment {
            command:
                ExperimentCommand::New {
                    name,
                    path,
                    data_root,
                    processed_root,
                    no_input,
                },
        } => run_experiment_new(name, path, data_root, processed_root, no_input),
    };
    match result
    {
        Ok(code) => code,
        Err(e) =>
        {
            eprintln!("error: {e}");
            // Exit 2 for genuine errors, so scripts can tell "check found
            // drift" (exit 1) from "the command itself failed".
            ExitCode::from(2)
        }
    }
}

struct NewArgs
{
    name: String,
    path: PathBuf,
    status: Option<Status>,
    owner: Option<String>,
    email: Option<String>,
    no_input: bool,
    force: bool,
}

fn run_new(args: NewArgs) -> Result<ExitCode, crate::Error>
{
    // Owner/email fall back to the machine config. A machine with no
    // resolvable config dir just gets no defaults; a *malformed* config file
    // is a real error the user should see.
    let machine = match config::machine_dirs()
    {
        Ok(dirs) => MachineConfig::load(&dirs.config_file)?,
        Err(_) => MachineConfig::default(),
    };
    let values = resolve_tokens(&args, &machine);
    let report = stamp(&NewOptions {
        name: args.name,
        parent: args.path,
        values,
        force: args.force,
    })?;
    println!(
        "Created {} ({} files, {} directories)",
        report.root.display(),
        report.files_written,
        report.dirs_created
    );
    if !report.unfilled.is_empty()
    {
        println!(
            "Unfilled tokens in context.md (fill by hand or leave for later): {}",
            report.unfilled.join(", ")
        );
    }
    Ok(ExitCode::SUCCESS)
}

/// Flags first, then the machine config's defaults; anything still missing is
/// prompted for unless prompting is disabled (`--no-input`, or stdin is not a
/// terminal). Empty answers skip the token.
fn resolve_tokens(args: &NewArgs, machine: &MachineConfig) -> TokenValues
{
    let mut values = TokenValues::new();
    let from_flags = [
        (Token::Owner, args.owner.as_ref().or(machine.owner.as_ref())),
        (
            Token::OwnerEmail,
            args.email.as_ref().or(machine.email.as_ref()),
        ),
    ];
    for (token, value) in from_flags
    {
        if let Some(value) = value
        {
            values.insert(token, value.clone());
        }
    }
    if let Some(status) = args.status
    {
        values.insert(Token::Status, status.as_str().to_string());
    }

    let interactive = !args.no_input && std::io::stdin().is_terminal();
    if !interactive
    {
        return values;
    }

    prompt_status(&mut values);
    prompt_text(&mut values, Token::Owner, "Owner");
    prompt_text(&mut values, Token::OwnerEmail, "Owner email");
    values
}

fn prompt_text(values: &mut TokenValues, token: Token, label: &str)
{
    if values.contains_key(&token)
    {
        return;
    }
    let answer: Result<String, _> = dialoguer::Input::new()
        .with_prompt(format!("{label} (Enter to skip)"))
        .allow_empty(true)
        .interact_text();
    if let Ok(answer) = answer
    {
        let answer = answer.trim().to_string();
        if !answer.is_empty()
        {
            values.insert(token, answer);
        }
    }
}

fn prompt_status(values: &mut TokenValues)
{
    if values.contains_key(&Token::Status)
    {
        return;
    }
    let mut items: Vec<&str> = Status::ALL.iter().map(|s| s.as_str()).collect();
    items.push("(skip)");
    if let Ok(index) = dialoguer::Select::new()
        .with_prompt("Status")
        .items(&items)
        .default(0)
        .interact()
        && index < Status::ALL.len()
    {
        values.insert(Token::Status, Status::ALL[index].as_str().to_string());
    }
}

struct SyncArgs
{
    mode: Option<SyncModeArg>,
    project: PathBuf,
    exclude: Vec<String>,
    mirror: bool,
    dry_run: bool,
}

/// The machine-side facts every sync-family command needs: this machine's
/// remote root plus, per project slug, the cache and log directories.
struct SyncContext
{
    remote_root: PathBuf,
    dirs: MachineDirs,
}

impl SyncContext
{
    /// Loads the machine config and validates the remote root exists (an
    /// absent root usually means the Drive/share is not mounted — failing
    /// here beats half-running a sync against a phantom path).
    fn resolve() -> Result<SyncContext, crate::Error>
    {
        let dirs = config::machine_dirs()?;
        let machine = MachineConfig::load(&dirs.config_file)?;
        let remote_root = machine
            .remote_root
            .ok_or_else(|| crate::Error::RemoteRootUnset(dirs.config_file.clone()))?;
        let remote_root = PathBuf::from(remote_root);
        if !remote_root.is_dir()
        {
            return Err(crate::Error::RemoteRootMissing(remote_root));
        }
        Ok(SyncContext { remote_root, dirs })
    }

    fn remote(&self, slug: &str) -> PathBuf
    {
        self.remote_root.join(slug)
    }

    fn cache(&self, slug: &str) -> PathBuf
    {
        self.dirs.cache_root.join(slug)
    }

    fn log_dir(&self, slug: &str) -> PathBuf
    {
        self.dirs.log_root.join(slug)
    }
}

fn run_sync(args: SyncArgs) -> Result<ExitCode, crate::Error>
{
    use crate::{
        manifest::Manifest,
        sync::{Mode, SyncOptions, sync},
        tokens::slugify,
    };

    // The slug comes from the manifest's project name, the one identifier
    // every machine holding this project agrees on.
    let manifest = Manifest::load(&args.project)?;
    let slug = slugify(&manifest.project).ok_or(crate::Error::BadSlug(manifest.project))?;
    let context = SyncContext::resolve()?;

    let options = SyncOptions {
        local: args.project,
        cache: context.cache(&slug),
        remote: context.remote(&slug),
        mode: match args.mode
        {
            None => Mode::Both,
            Some(SyncModeArg::Push) => Mode::Push,
            Some(SyncModeArg::Pull) => Mode::Pull,
        },
        exclude: args.exclude,
        mirror: args.mirror,
        dry_run: args.dry_run,
        log_dir: context.log_dir(&slug),
    };

    if options.mirror && !options.dry_run
    {
        eprintln!("warning: --mirror DELETES files at the target that are absent from the source");
    }

    let report = sync(&options)?;
    println!("{}", report.summary);
    println!("History: {}", report.history_log.display());
    println!("Detail:  {}", report.detail_log.display());
    Ok(ExitCode::SUCCESS)
}

fn run_clone(name: String, path: PathBuf) -> Result<ExitCode, crate::Error>
{
    use crate::{
        sync::{CloneOptions, clone_project},
        tokens::slugify,
    };

    let slug = slugify(&name).ok_or_else(|| crate::Error::BadSlug(name.clone()))?;
    let context = SyncContext::resolve()?;
    let target = path.join(&slug);

    let report = clone_project(&CloneOptions {
        remote: context.remote(&slug),
        cache: context.cache(&slug),
        target: target.clone(),
        log_dir: context.log_dir(&slug),
    })?;
    println!("Cloned into {}", target.display());
    println!("{}", report.summary);
    Ok(ExitCode::SUCCESS)
}

fn run_config(
    owner: Option<String>,
    email: Option<String>,
    remote_root: Option<String>,
) -> Result<ExitCode, crate::Error>
{
    let dirs = config::machine_dirs()?;
    let mut machine = MachineConfig::load(&dirs.config_file)?;

    let changed = owner.is_some() || email.is_some() || remote_root.is_some();
    if let Some(owner) = owner
    {
        machine.owner = Some(owner);
    }
    if let Some(email) = email
    {
        machine.email = Some(email);
    }
    if let Some(remote_root) = remote_root
    {
        machine.remote_root = Some(remote_root);
    }
    if changed
    {
        machine.save(&dirs.config_file)?;
    }

    let show = |value: &Option<String>| value.as_deref().unwrap_or("(unset)").to_string();
    println!("Config file: {}", dirs.config_file.display());
    println!("owner       = {}", show(&machine.owner));
    println!("email       = {}", show(&machine.email));
    println!("remote_root = {}", show(&machine.remote_root));
    if machine.remote_root.is_none()
    {
        println!("Set the sync remote once per machine: exporgo config --remote-root <path>");
    }
    Ok(ExitCode::SUCCESS)
}

fn run_experiment_new(
    name: String,
    path: PathBuf,
    data_root: Option<String>,
    processed_root: Option<String>,
    no_input: bool,
) -> Result<ExitCode, crate::Error>
{
    use crate::experiment::{NewExperimentOptions, stamp_experiment};

    // Data roots are per-experiment hints; both are skippable prompts.
    let mut data_root = data_root;
    let mut processed_root = processed_root;
    let interactive = !no_input && std::io::stdin().is_terminal();
    if interactive
    {
        let prompt = |label: &str| -> Option<String> {
            let answer: Result<String, _> = dialoguer::Input::new()
                .with_prompt(format!("{label} (Enter to skip)"))
                .allow_empty(true)
                .interact_text();
            answer
                .ok()
                .map(|a| a.trim().to_string())
                .filter(|a| !a.is_empty())
        };
        if data_root.is_none()
        {
            data_root = prompt("Raw data root");
        }
        if processed_root.is_none()
        {
            processed_root = prompt("Processed data root");
        }
    }

    let report = stamp_experiment(&NewExperimentOptions {
        project_root: path,
        name,
        raw_data_root: data_root,
        processed_data_root: processed_root,
    })?;
    println!(
        "Created {} ({} files)",
        report.dir.display(),
        report.files_written
    );
    if !report.unfilled.is_empty()
    {
        println!(
            "Unfilled tokens (fill by hand or leave for later): {}",
            report.unfilled.join(", ")
        );
    }
    Ok(ExitCode::SUCCESS)
}

fn run_check(path: PathBuf) -> Result<ExitCode, crate::Error>
{
    let report = check(&path)?;
    if report.project_version == report.binary_version
    {
        println!("Template version: {} (current)", report.project_version);
    }
    else if report.project_version > report.binary_version
    {
        println!(
            "Template version: project {} is NEWER than this binary {} — download a newer release",
            report.project_version, report.binary_version
        );
    }
    else
    {
        println!(
            "Template version: project {} → binary {}",
            report.project_version, report.binary_version
        );
    }
    print_changes("Update would apply", &report.changes);
    if !report.unfilled_tokens.is_empty()
    {
        println!(
            "Unfilled tokens in context.md: {}",
            report.unfilled_tokens.join(", ")
        );
    }
    if !report.missing_dirs.is_empty()
    {
        println!(
            "Missing standard directories: {}",
            report.missing_dirs.join(", ")
        );
    }
    if report.is_clean()
    {
        println!("Project is up to date.");
        Ok(ExitCode::SUCCESS)
    }
    else
    {
        Ok(ExitCode::FAILURE)
    }
}

fn run_update(path: PathBuf, options: UpdateOptions) -> Result<ExitCode, crate::Error>
{
    let dry_run = options.dry_run;
    let changes = update(&path, &options)?;
    if dry_run
    {
        print_changes("Would apply", &changes);
    }
    else if changes.is_empty()
    {
        println!("Already up to date.");
    }
    else
    {
        print_changes("Applied", &changes);
    }
    Ok(ExitCode::SUCCESS)
}

fn print_changes(heading: &str, changes: &[PlannedChange])
{
    if changes.is_empty()
    {
        return;
    }
    println!("{heading} ({} files):", changes.len());
    for change in changes
    {
        let kind = match change.kind
        {
            ChangeKind::Create => "create",
            ChangeKind::Overwrite => "overwrite",
        };
        println!("  {kind:9} {}", change.rel);
    }
}

#[cfg(test)]
mod tests
{
    use pretty_assertions::assert_eq;

    use super::*;

    fn new_args() -> NewArgs
    {
        NewArgs {
            name: "Pilot".to_string(),
            path: PathBuf::from("."),
            status: Some(Status::Analysis),
            owner: Some("Darik".to_string()),
            email: Some("doneil@salk.edu".to_string()),
            no_input: true, // never prompt in tests
            force: false,
        }
    }

    #[test]
    fn resolve_tokens_maps_every_flag_to_its_token()
    {
        let values = resolve_tokens(&new_args(), &MachineConfig::default());
        let expected: [(Token, &str); 3] = [
            (Token::Status, "analysis"),
            (Token::Owner, "Darik"),
            (Token::OwnerEmail, "doneil@salk.edu"),
        ];
        for (token, value) in expected
        {
            assert_eq!(values.get(&token).map(String::as_str), Some(value));
        }
        // Name and created date are stamp's job, never the flag resolver's.
        assert!(!values.contains_key(&Token::ProjectName));
        assert!(!values.contains_key(&Token::CreatedDate));
    }

    #[test]
    fn absent_flags_leave_tokens_unset()
    {
        let mut args = new_args();
        args.owner = None;
        args.status = None;
        let values = resolve_tokens(&args, &MachineConfig::default());
        assert!(!values.contains_key(&Token::Owner));
        assert!(!values.contains_key(&Token::Status));
        assert_eq!(values.len(), 1);
    }

    /// The machine config supplies owner/email defaults; explicit flags beat
    /// it.
    #[test]
    fn machine_config_fills_owner_and_email_but_never_overrides_flags()
    {
        let machine = MachineConfig {
            owner: Some("Config Owner".to_string()),
            email: Some("config@salk.edu".to_string()),
            remote_root: None,
        };

        let mut args = new_args();
        args.owner = None;
        args.email = None;
        let values = resolve_tokens(&args, &machine);
        assert_eq!(
            values.get(&Token::Owner).map(String::as_str),
            Some("Config Owner")
        );
        assert_eq!(
            values.get(&Token::OwnerEmail).map(String::as_str),
            Some("config@salk.edu")
        );

        let values = resolve_tokens(&new_args(), &machine);
        assert_eq!(values.get(&Token::Owner).map(String::as_str), Some("Darik"));
        assert_eq!(
            values.get(&Token::OwnerEmail).map(String::as_str),
            Some("doneil@salk.edu")
        );
    }

    /// The status vocabulary is a contract with the template's context.md
    /// ("planning | active | analysis | writing | archived").
    #[test]
    fn status_strings_match_the_template_vocabulary()
    {
        let rendered: Vec<&str> = Status::ALL.iter().map(|s| s.as_str()).collect();
        assert_eq!(
            rendered,
            vec!["planning", "active", "analysis", "writing", "archived"]
        );
    }
}
